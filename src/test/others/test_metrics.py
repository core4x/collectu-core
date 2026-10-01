"""
The performance metrics of the modules and of the flows through a pipeline (metrics.py).
"""
import gc
import json
import queue
import threading
import types
import unittest
from unittest import mock

# Internal imports.
import metrics
import models
from metrics import (_AtomicInt, _CircularStats, _DataContext, _DataContextMap, _SlidingWindow, MetricsRegistry,
                     ModuleMetrics, metrics_registry)
from test.helpers import GlobalStateTestCase


class _Clock:
    """
    Stands in for time.monotonic in metrics.py, and is moved forward by the test.
    """

    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def _use_clock(test: unittest.TestCase) -> _Clock:
    clock = _Clock()
    patcher = mock.patch.object(metrics, "time", types.SimpleNamespace(monotonic=clock))
    patcher.start()
    test.addCleanup(patcher.stop)
    return clock


class TestSlidingWindow(unittest.TestCase):
    """
    Counts events, and how many of them happened within the last seconds.
    """

    def setUp(self):
        self.clock = _use_clock(self)

    def test_the_rate_is_the_number_of_events_per_second_within_the_window(self):
        window = _SlidingWindow()
        for _ in range(3):
            window.record()
        self.assertEqual(window.rate(1), 3.0)
        self.assertAlmostEqual(window.rate(10), 0.3)
        self.assertAlmostEqual(window.rate(), 3 / 60, msg="The rate is taken over the whole window by default.")

    def test_events_leave_the_rate_as_time_passes_but_stay_in_the_total(self):
        window = _SlidingWindow()
        window.record()
        self.clock.now += 5
        window.record()
        self.assertEqual(window.rate(1), 1.0)
        self.assertEqual(window.rate(10), 0.2)
        self.clock.now += 120
        self.assertEqual(window.rate(60), 0.0)
        self.assertEqual(window.total, 2)

    def test_events_older_than_the_window_are_dropped(self):
        window = _SlidingWindow(window=60)
        window.record()
        self.clock.now += 61
        window.record()
        self.assertEqual(len(window._dq), 1)
        self.assertEqual(window.total, 2)

    def test_an_empty_window_has_no_rate(self):
        window = _SlidingWindow()
        window.record()
        self.assertEqual(window.rate(0), 0.0)
        self.assertEqual(window.rate(-1), 0.0)


class TestCircularStats(unittest.TestCase):
    """
    Keeps the latest samples, for their mean and percentiles.
    """

    def test_nothing_is_known_without_samples(self):
        stats = _CircularStats()
        self.assertEqual((stats.percentile(50), stats.mean, stats.count), (None, None, 0))

    def test_percentiles_are_taken_by_nearest_rank(self):
        stats = _CircularStats()
        for value in range(100, 0, -1):
            stats.record(float(value))
        self.assertEqual([stats.percentile(p) for p in (0, 50, 95, 99, 100)], [1.0, 51.0, 96.0, 100.0, 100.0])
        self.assertEqual(stats.mean, 50.5)
        self.assertEqual(stats.count, 100)

    def test_the_oldest_samples_are_dropped_once_it_is_full(self):
        stats = _CircularStats(maxlen=3)
        for value in (1.0, 2.0, 3.0, 4.0):
            stats.record(value)
        self.assertEqual((stats.count, stats.mean, stats.percentile(0)), (3, 3.0, 2.0))


class TestAtomicInt(unittest.TestCase):

    def test_concurrent_increments_are_all_counted(self):
        counter = _AtomicInt()

        def increment():
            for _ in range(1000):
                counter.inc()

        threads = [threading.Thread(target=increment) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        counter.inc(5)
        self.assertEqual(counter.value, 8005)


class TestModuleMetrics(unittest.TestCase):

    def test_a_snapshot_reports_in_milliseconds(self):
        module_metrics = ModuleMetrics(module_id="output", module_name="outputs.test.collector_1")
        module_metrics.record_received()
        module_metrics.record_processed()
        module_metrics.record_processing_time(0.0015)
        module_metrics.record_link_wait(0.002)
        module_metrics.record_internal_wait(0.25)

        snapshot = module_metrics.snapshot()

        self.assertEqual((snapshot["module_id"], snapshot["module_name"]), ("output", "outputs.test.collector_1"))
        self.assertEqual(snapshot["processing_time_ms"], {"p50": 1.5, "p95": 1.5, "p99": 1.5, "mean": 1.5,
                                                          "sample_count": 1})
        self.assertEqual(snapshot["link_queue_wait_ms"]["mean"], 2.0)
        self.assertEqual(snapshot["internal_queue_wait_ms"]["mean"], 250.0)
        self.assertEqual((snapshot["throughput"]["received_total"], snapshot["throughput"]["processed_total"]),
                         (1, 1))
        json.dumps(snapshot)

    def test_negative_durations_are_ignored(self):
        """
        Two monotonic readings on different threads can be a hair out of order.
        """
        module_metrics = ModuleMetrics(module_id="output", module_name="outputs.test.collector_1")
        module_metrics.record_processing_time(-0.001)
        module_metrics.record_link_wait(-0.001)
        module_metrics.record_internal_wait(-0.001)
        snapshot = module_metrics.snapshot()
        for key in ("processing_time_ms", "link_queue_wait_ms", "internal_queue_wait_ms"):
            self.assertEqual(snapshot[key]["sample_count"], 0, key)

    def test_errors_and_drops_are_counted(self):
        module_metrics = ModuleMetrics(module_id="output", module_name="outputs.test.collector_1")
        module_metrics.record_error()
        module_metrics.record_drop()
        module_metrics.record_drop(3)
        module_metrics.record_drop(0)
        self.assertEqual(module_metrics.snapshot()["errors"], {"error_total": 1, "drop_total": 4})

    def test_the_depth_of_the_queue_of_the_module_is_reported(self):
        module_queue = queue.Queue()
        module_queue.put(1)
        self.assertEqual(ModuleMetrics("a", "outputs.a", queue=module_queue).snapshot()["queue"],
                         {"current_depth": 1})
        self.assertEqual(ModuleMetrics("b", "processors.b").snapshot()["queue"], {"current_depth": None})


class TestMetricsRegistry(GlobalStateTestCase):

    def test_there_is_one_registry(self):
        self.assertIs(MetricsRegistry(), metrics_registry)

    def test_a_module_is_registered_once(self):
        first = metrics_registry.register(module_id="output", module_name="outputs.test.collector_1")
        self.assertIs(metrics_registry.register(module_id="output", module_name="outputs.test.collector_1"), first)
        self.assertIs(metrics_registry.get("output"), first)
        self.assertIsNone(metrics_registry.get("unknown"))

    def test_a_reset_forgets_everything(self):
        metrics_registry.register(module_id="output", module_name="outputs.test.collector_1")
        metrics_registry.record_end_to_end(source_id="source", output_id="output", seconds=0.1)
        metrics_registry.reset()
        self.assertEqual(metrics_registry.snapshot(), {"modules": [], "flows": {}})

    def test_flows_are_measured_per_source_and_output(self):
        metrics_registry.record_end_to_end(source_id="source", output_id="first", seconds=0.1)
        metrics_registry.record_end_to_end(source_id="source", output_id="first", seconds=0.3)
        metrics_registry.record_end_to_end(source_id="source", output_id="second", seconds=0.2)
        metrics_registry.record_end_to_end(source_id="source", output_id="third", seconds=-1)

        flows = metrics_registry.snapshot()["flows"]

        self.assertEqual(sorted(flows), ["source->first", "source->second"])
        latency = flows["source->first"]["end_to_end_latency_ms"]
        self.assertEqual((latency["mean"], latency["sample_count"], latency["p99"]), (200.0, 2, 300.0))

    def test_the_overall_performance_without_modules(self):
        self.assertEqual(metrics_registry.overall_performance(),
                         {"processed_per_min_min": None, "processed_per_min_max": None,
                          "processed_per_min_avg": None, "module_count": 0})

    def test_the_overall_performance_is_taken_across_all_modules(self):
        clock = _use_clock(self)
        busy = metrics_registry.register(module_id="busy", module_name="processors.busy")
        metrics_registry.register(module_id="idle", module_name="processors.idle")
        for _ in range(6):
            busy.record_processed()
        clock.now += 1

        self.assertEqual(metrics_registry.overall_performance(),
                         {"processed_per_min_min": 0.0, "processed_per_min_max": 6.0,
                          "processed_per_min_avg": 3.0, "module_count": 2})

    def test_a_snapshot_can_be_serialized(self):
        metrics_registry.register(module_id="output", module_name="outputs.test.collector_1", queue=queue.Queue())
        metrics_registry.record_end_to_end(source_id="source", output_id="output", seconds=0.1)
        snapshot = metrics_registry.snapshot()
        self.assertEqual([module["module_id"] for module in snapshot["modules"]], ["output"])
        self.assertEqual(json.loads(json.dumps(snapshot)), snapshot)


class TestDataContextMap(unittest.TestCase):
    """
    The timing of a data object is kept beside it rather than on it, so it never reaches a serialization of the data.
    """

    def setUp(self):
        self.contexts = _DataContextMap()
        self.context = _DataContext(pipeline_ts=1.0, source_id="source", link_ts=2.0, visited=frozenset({"source"}))

    @staticmethod
    def _data() -> models.Data:
        return models.Data(measurement="test", fields={"value": 1})

    def test_a_context_is_kept_for_its_data_object(self):
        data = self._data()
        self.contexts.set(data, self.context)
        self.assertIs(self.contexts.get(data), self.context)
        self.assertIsNone(self.contexts.get(self._data()))
        self.assertNotIn("source", data.__dict__.values(), "The context leaked into the data object.")

    def test_the_context_is_forgotten_with_its_data_object(self):
        data = self._data()
        self.contexts.set(data, self.context)
        del data
        gc.collect()
        self.assertEqual(self.contexts._map, {})

    def test_objects_without_weak_references_are_not_kept(self):
        for value in (None, 1, "text"):
            self.contexts.set(value, self.context)
            self.assertIsNone(self.contexts.get(value))

    def test_a_new_data_object_takes_over_the_context_of_the_one_it_replaces(self):
        old, new = self._data(), self._data()
        self.contexts.set(old, self.context)
        self.contexts.propagate(old, new)
        self.assertIs(self.contexts.get(new), self.context)

    def test_a_context_is_not_overwritten_by_propagation(self):
        old, new = self._data(), self._data()
        own = _DataContext(pipeline_ts=5.0, source_id="other", link_ts=5.0)
        self.contexts.set(old, self.context)
        self.contexts.set(new, own)
        self.contexts.propagate(old, new)
        self.assertIs(self.contexts.get(new), own)

    def test_there_is_nothing_to_propagate_without_a_context(self):
        old, new = self._data(), self._data()
        self.contexts.propagate(old, new)
        self.contexts.propagate(new, new)
        self.assertIsNone(self.contexts.get(new))

    def test_the_remaining_links_are_the_ones_not_visited(self):
        self.assertEqual(self.context.remaining({"source", "output"}), {"output"})
        self.assertEqual(self.context.remaining({"source"}), set())


if __name__ == '__main__':
    unittest.main()
