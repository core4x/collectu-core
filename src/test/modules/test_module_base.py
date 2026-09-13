import logging
import queue
import random
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

# Internal imports.
import config
import data_layer
import models
from configuration import Configuration
from metrics import metrics_registry, data_context_map, _DataContext
from modules.base.base import AbstractModule, ModuleWorker, QueueMonitor
from modules.base.outputs.base import AbstractOutputModule
from modules.base.processors.base import AbstractProcessorModule


def _levels(logs) -> list[str]:
    """Returns the level names of the captured log records in order."""
    return [record.levelname for record in logs.records]


def _messages(logs, level: str) -> list[str]:
    """Returns the messages of the captured log records with the given level."""
    return [record.getMessage() for record in logs.records if record.levelname == level]


class _Module(AbstractModule):
    pass


class _Output(AbstractOutputModule):
    def _run(self, data: models.Data):
        pass


class _Processor(AbstractProcessorModule):
    def _run(self, data: models.Data) -> models.Data:
        return data


class _BlockingModule:
    """A linked module whose run blocks until released, so the queue of a link to it fills up."""

    def __init__(self):
        self.active = True
        self.running = threading.Event()
        self.release = threading.Event()

    def run(self, data: models.Data):
        self.running.set()
        self.release.wait(timeout=10)


class _WatchedEvent(threading.Event):
    """An event which tells when a thread started waiting for it."""

    def __init__(self):
        super().__init__()
        self.awaited = threading.Event()

    def wait(self, timeout=None):
        self.awaited.set()
        return super().wait(timeout)


class _Recorder:
    """Records the values of the data objects passed to it, and how many calls overlapped at most."""

    def __init__(self, delay: float = 0.0):
        self.values: list[int] = []
        self.max_overlap = 0
        self._delay = delay
        self._running = 0
        self._condition = threading.Condition()

    def record(self, data: models.Data):
        with self._condition:
            self._running += 1
            self.max_overlap = max(self.max_overlap, self._running)
        time.sleep(self._delay)
        with self._condition:
            self._running -= 1
            self.values.append(data.fields["value"])
            self._condition.notify_all()

    def wait_for(self, count: int, timeout: float = 5) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: len(self.values) >= count, timeout=timeout)


class _RecordingOutput(AbstractOutputModule):
    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.recorder = _Recorder()

    def _run(self, data: models.Data):
        self.recorder.record(data)


class _RecordingProcessor(AbstractProcessorModule):
    def __init__(self, configuration):
        super().__init__(configuration=configuration, thread_safe=True)
        self.recorder = _Recorder()

    def _run(self, data: models.Data) -> models.Data:
        self.recorder.record(data)
        return data


class _GlobalState(unittest.TestCase):
    """Restores the data layer, the metrics registry and the patched limits after each test."""

    def setUp(self):
        patcher = mock.patch.multiple(config, WARNING_LIMIT=10, STOP_LIMIT=10000, SLOW_WORKER_TIMEOUT=60,
                                      STOP_TIMEOUT=1, START_TIMEOUT=60)
        patcher.start()
        self.addCleanup(patcher.stop)
        saved = (data_layer.module_data, data_layer.running, data_layer.buffer_instance)
        self.addCleanup(self._restore, saved)
        data_layer.module_data = {}
        data_layer.running = True
        data_layer.buffer_instance = None
        metrics_registry.reset()
        self.addCleanup(metrics_registry.reset)

    @staticmethod
    def _restore(saved):
        data_layer.module_data, data_layer.running, data_layer.buffer_instance = saved

    @staticmethod
    def _data(value: int = 1) -> models.Data:
        return models.Data(measurement="test", fields={"value": value})

    @staticmethod
    def _drops(module_id: str) -> int:
        return metrics_registry.get(module_id).snapshot()["errors"]["drop_total"]


class TestQueueMonitor(_GlobalState):
    """
    The monitor decides what the log of a filling queue looks like: every message once, however many
    threads report the same state, and no repetition while the fill level oscillates around a limit.
    """

    def setUp(self):
        super().setUp()
        self.logger = logging.getLogger("test.queue_monitor")
        self.monitor = QueueMonitor(logger=self.logger, name="linked module 'target'")

    @staticmethod
    def _concurrently(call, threads: int = 16):
        barrier = threading.Barrier(threads)

        def target():
            barrier.wait()
            call()

        started = [threading.Thread(target=target) for _ in range(threads)]
        for thread in started:
            thread.start()
        for thread in started:
            thread.join()

    def test_concurrent_reports_are_logged_once(self):
        with self.assertLogs(self.logger, level="WARNING") as logs:
            self._concurrently(lambda: self.monitor.update(size=10))
            self._concurrently(lambda: self.monitor.record_drop())
        self.assertEqual(_levels(logs), ["WARNING", "ERROR"])

    def test_warning_limit_hysteresis(self):
        with self.assertLogs(self.logger, level="INFO") as logs:
            # Oscillating around the warning limit, but never below half of it.
            for size in (10, 9, 10, 9, 10, 5, 10):
                self.monitor.update(size=size)
            self.monitor.update(size=4)
            self.monitor.update(size=10)
        self.assertEqual(_levels(logs), ["WARNING", "INFO", "WARNING"])
        self.assertEqual(_messages(logs, "WARNING")[0],
                         "Queue for linked module 'target' is filling up (10/10000 data objects).")

    def test_each_multiple_is_reported_once(self):
        with self.assertLogs(self.logger, level="WARNING") as logs:
            for size in (10, 20, 15, 20, 25, 30, 21, 30):
                self.monitor.update(size=size)
        self.assertEqual(len(logs.records), 3)

    def test_stop_limit_hysteresis(self):
        with self.assertLogs(self.logger, level="INFO") as logs:
            for _ in range(5):
                self.monitor.record_drop()
            # Less than 1 % below the stop limit.
            self.monitor.update(size=9950)
            self.monitor.record_drop()
            self.monitor.update(size=9899)
        self.assertEqual(_levels(logs), ["ERROR", "INFO"])
        self.assertEqual(_messages(logs, "INFO"), [
            "Queue for linked module 'target' is back below the stop limit. "
            "Dropped 6 data object(s) in the meantime."])

    def test_blocked_worker_keeps_the_link_full(self):
        blocked, idle = object(), object()
        with self.assertLogs(self.logger, level="INFO") as logs:
            for _ in range(3):
                self.monitor.record_drop(key=blocked)
                self.monitor.update(size=0, key=idle)
        self.assertEqual(_levels(logs), ["ERROR"])

    def test_slow_workers_of_a_link_warn_once(self):
        first, second = object(), object()
        with self.assertLogs(self.logger, level="WARNING") as logs:
            self.monitor.update_worker(key=first, busy_for=61.0)
            self.monitor.update_worker(key=second, busy_for=61.0)
            self.monitor.update_worker(key=first, busy_for=None)
            self.monitor.update_worker(key=first, busy_for=62.0)  # The second one was not seen idle yet.
            self.monitor.update_worker(key=first, busy_for=None)
            self.monitor.update_worker(key=second, busy_for=None)
            self.monitor.update_worker(key=second, busy_for=1.0)  # Below the threshold.
            self.monitor.update_worker(key=second, busy_for=61.0)
        self.assertEqual(len(logs.records), 2)


class TestDropsAreRecorded(_GlobalState):
    """
    Every data object discarded before the module it was meant for could process it counts as a drop
    of that module - on a link, as well as in the queue of the module itself.
    """

    def setUp(self):
        super().setUp()
        config.STOP_LIMIT = 5  # Restored by the patcher.
        self.logger = logging.getLogger("test.module_worker")
        self.target = _BlockingModule()
        self.addCleanup(self.target.release.set)
        data_layer.module_data["target"] = SimpleNamespace(instance=self.target, latest_data=None)
        metrics_registry.register(module_id="target", module_name="outputs.test")

    def _busy_worker(self, forward_latest_data_only: bool = False) -> ModuleWorker:
        """Returns a worker which is blocked inside the run method of the linked module."""
        worker = ModuleWorker(configuration_id="source", module_id="target", logger=self.logger,
                              forward_latest_data_only=forward_latest_data_only)
        worker.submit(self._data())
        self.assertTrue(self.target.running.wait(timeout=5), "The worker did not pick up the first data object.")
        return worker

    def test_full_link_queue(self):
        worker = self._busy_worker()
        with self.assertLogs(self.logger, level="ERROR") as logs:
            for _ in range(config.STOP_LIMIT + 3):
                worker.submit(self._data())
        self.assertEqual(self._drops("target"), 3)
        self.assertEqual(len(logs.records), 1)

        with self.assertLogs(self.logger, level="WARNING"):
            # The queue is full, so there is no sentinel: the whole backlog is dropped at the deadline.
            worker.signal_stop(timeout=0)
            self.target.release.set()
            self.assertTrue(worker.join(timeout=5))
        self.assertEqual(self._drops("target"), 3 + config.STOP_LIMIT)

    def test_backlog_dropped_on_stop_without_the_sentinel(self):
        worker = self._busy_worker()
        worker.submit(self._data())
        worker.submit(self._data())
        with self.assertLogs(self.logger, level="WARNING") as logs:
            worker.signal_stop(timeout=0)
            self.target.release.set()
            self.assertTrue(worker.join(timeout=5))
        self.assertEqual(self._drops("target"), 2)
        self.assertIn("Dropping 2 data object(s)", logs.records[0].getMessage())

    def test_replaced_data_in_latest_only_mode(self):
        worker = self._busy_worker(forward_latest_data_only=True)
        for _ in range(3):
            worker.submit(self._data())  # The first one waits, the other two replace it in turn.
        self.assertEqual(self._drops("target"), 2)
        worker.signal_stop(timeout=0)  # Discards the one still waiting.
        self.target.release.set()
        self.assertTrue(worker.join(timeout=5))
        self.assertEqual(self._drops("target"), 3)

    def _assert_full_module_queue(self, module):
        data_layer.module_data[module.configuration.id] = SimpleNamespace(instance=module, latest_data=None)
        # Without a queue worker, nothing works the queue off.
        with mock.patch.object(module._queue_worker, "start"), self.assertLogs(module.logger, level="ERROR") as logs:
            for _ in range(config.STOP_LIMIT + 3):
                module.run(self._data())
        self.assertEqual(self._drops(module.configuration.id), 3)
        self.assertEqual(len(logs.records), 1)

    def test_full_output_queue(self):
        self._assert_full_module_queue(
            _Output(SimpleNamespace(id="output", module_name="outputs.test", active=True)))

    def test_full_processor_queue(self):
        self._assert_full_module_queue(
            _Processor(SimpleNamespace(id="processor", module_name="processors.test", active=True), thread_safe=True))


class TestMetricsBookkeeping(_GlobalState):

    def test_re_registered_module_reports_its_new_queue(self):
        old_queue, new_queue = queue.Queue(), queue.Queue()
        new_queue.put(1)
        first = metrics_registry.register(module_id="module", module_name="outputs.old", queue=old_queue)
        second = metrics_registry.register(module_id="module", module_name="outputs.new", queue=new_queue)
        self.assertIs(first, second)
        self.assertEqual(second.snapshot()["module_name"], "outputs.new")
        self.assertEqual(second.snapshot()["queue"]["current_depth"], 1)

    def test_no_context_is_stored_for_objects_without_weak_references(self):
        data_context_map.set(None, _DataContext(pipeline_ts=0.0, source_id="source", link_ts=0.0))
        self.assertIsNone(data_context_map.get(None))

    def test_only_forwarded_data_ends_a_flow(self):
        module = _Module(SimpleNamespace(id="sink", module_name="processors.test", active=True, links=[]))
        data_layer.module_data["sink"] = SimpleNamespace(instance=module, latest_data=None)

        module._call_links(self._data())
        self.assertEqual(metrics_registry.snapshot()["flows"], {})

        forwarded = self._data()
        data_context_map.set(forwarded, _DataContext(pipeline_ts=time.monotonic(), source_id="source",
                                                     link_ts=time.monotonic(), visited=frozenset({"source"})))
        module._call_links(forwarded)
        self.assertEqual(list(metrics_registry.snapshot()["flows"]), ["source->sink"])


class TestRestartInPlace(_GlobalState):
    """
    Configuration.start_module restarts an existing module without a new configuration in place: the same
    instance is stopped, activated again and started. Its link workers and its queue worker have to be back -
    exactly once, however the restart interleaves with the threads of the previous run.
    """

    @staticmethod
    def _register(instance) -> SimpleNamespace:
        entry = SimpleNamespace(instance=instance, configuration=instance.configuration,
                                module_name=instance.configuration.module_name, latest_data=None)
        data_layer.module_data[instance.configuration.id] = entry
        return entry

    @staticmethod
    def _reactivate(entry: SimpleNamespace):
        """The part of Configuration.start_module which restarts a stopped module in place."""
        entry.instance.active = True
        Configuration._start_module(entry)

    @staticmethod
    def _threads(name: str) -> list[str]:
        """Returns the names of the running threads starting with the given name."""
        return [thread.name for thread in threading.enumerate() if thread.name.startswith(name)]

    @staticmethod
    def _deactivate(module):
        """Lets the queue worker of the module leave - it is not a daemon thread."""
        module.active = False
        for thread in threading.enumerate():
            if thread.name == f"Queue_Worker_{module.configuration.id}":
                thread.join(timeout=5)

    @staticmethod
    def _target() -> _Recorder:
        """Registers a linked module with the id 'target', which records what it receives."""
        target = _Recorder()
        data_layer.module_data["target"] = SimpleNamespace(instance=SimpleNamespace(active=True, run=target.record))
        return target

    def test_link_workers_are_recreated(self):
        for latest_only in (False, True):
            with self.subTest(forward_latest_data_only=latest_only):
                target = self._target()
                source_id = f"source_{int(latest_only)}"
                source = _Module(SimpleNamespace(id=source_id, module_name="inputs.test", active=True,
                                                 links=["target"], worker_count_per_link=2,
                                                 forward_latest_data_only=latest_only))
                entry = self._register(source)
                self.addCleanup(source.stop)

                source._call_links(self._data(1))
                self.assertTrue(target.wait_for(1))
                Configuration._stop_module(entry)
                self.assertEqual(self._threads(f"Link_{source_id}_to_"), [])

                self._reactivate(entry)
                source._call_links(self._data(2))
                self.assertTrue(target.wait_for(2), "Nothing was forwarded after the restart.")
                self.assertEqual(target.values, [1, 2])
                self.assertEqual(len(self._threads(f"Link_{source_id}_to_")), 2)

    def test_module_stopped_meanwhile_gets_no_link_workers(self):
        target = self._target()
        source = _Module(SimpleNamespace(id="source", module_name="inputs.test", active=True, links=["target"]))
        self._register(source)
        self.addCleanup(source.stop)
        source._call_links(self._data(1))
        self.assertTrue(target.wait_for(1))

        get = data_context_map.get

        def stop_meanwhile(data):
            # _call_links looks up the context after checking that the module is active, so this is a stop
            # routine overtaking it right before it takes the lock to create the missing workers.
            source.active = False
            source.stop()
            return get(data)

        with mock.patch.object(data_context_map, "get", side_effect=stop_meanwhile):
            source._call_links(self._data(2))
        self.assertEqual(self._threads("Link_source_to_"), [])

    def test_queue_worker_is_restarted_once(self):
        for cls in (_RecordingOutput, _RecordingProcessor):
            for old_worker_left in (True, False):
                with self.subTest(module=cls.__name__, old_worker_left=old_worker_left):
                    module_id = f"{cls.__name__}_{int(old_worker_left)}"
                    module = cls(SimpleNamespace(id=module_id, module_name="test.module", active=True, links=[]))
                    entry = self._register(module)
                    self.addCleanup(self._deactivate, module)
                    module.started.set()
                    module.run(self._data(1))
                    self.assertTrue(module.recorder.wait_for(1))
                    old_worker = module._queue_worker._thread

                    if old_worker_left:
                        Configuration._stop_module(entry)
                        old_worker.join(timeout=5)
                        self.assertFalse(old_worker.is_alive(), "The queue worker did not leave after the stop.")
                        self._reactivate(entry)
                    else:
                        # Keeps the queue worker from noticing the stop before the module is active again.
                        with module._queue_worker._lock:
                            Configuration._stop_module(entry)
                            entry.instance.active = True
                        Configuration._start_module(entry)

                    module.run(self._data(2))
                    self.assertTrue(module.recorder.wait_for(2), "Nothing was processed after the restart.")
                    self.assertEqual(module.recorder.values, [1, 2])
                    self.assertEqual(self._threads(f"Queue_Worker_{module_id}"), [f"Queue_Worker_{module_id}"])
                    # A queue worker which did not notice the stop carries on, no second one is started.
                    self.assertEqual(module._queue_worker._thread is old_worker, not old_worker_left)

    def test_nothing_is_processed_without_readiness_across_a_stop(self):
        for cls in (_RecordingOutput, _RecordingProcessor):
            with self.subTest(module=cls.__name__):
                module = cls(SimpleNamespace(id=cls.__name__, module_name="test.module", active=True, links=[]))
                module.started = _WatchedEvent()
                entry = self._register(module)
                self.addCleanup(self._deactivate, module)
                module.run(self._data(1))  # The module never reported to be ready, so the data waits.
                worker = module._queue_worker._thread
                self.assertTrue(module.started.awaited.wait(timeout=5), "The queue worker did not wait for readiness.")

                Configuration._stop_module(entry)
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive(), "The queue worker did not leave after the stop.")
                self.assertEqual(module.recorder.values, [], "Data was processed without the module being ready.")

                self._reactivate(entry)
                module.run(self._data(2))
                self.assertTrue(module.recorder.wait_for(2), "Nothing was processed after the restart.")
                self.assertEqual(module.recorder.values, [1, 2])

    def test_restarts_under_load(self):
        # Restored by the patcher. Nothing is dropped, so all data has to arrive - and nothing is logged.
        config.STOP_LIMIT = config.WARNING_LIMIT = 1_000_000
        for cls in (_RecordingOutput, _RecordingProcessor):
            with self.subTest(module=cls.__name__):
                module = cls(SimpleNamespace(id=cls.__name__, module_name="test.module", active=True, links=[]))
                module.recorder = _Recorder(delay=0.0005)
                entry = self._register(module)
                self.addCleanup(self._deactivate, module)
                module.started.set()
                done = threading.Event()

                def produce(first_value: int):
                    value = first_value
                    while not done.is_set():
                        module.run(self._data(value))
                        value += 1
                        time.sleep(0.0002)

                producers = [threading.Thread(target=produce, args=(index * 1_000_000,)) for index in range(3)]
                for producer in producers:
                    producer.start()
                try:
                    for _ in range(25):
                        Configuration._stop_module(entry)
                        time.sleep(random.uniform(0, 0.005))
                        self._reactivate(entry)
                        time.sleep(random.uniform(0, 0.005))
                finally:
                    done.set()
                    for producer in producers:
                        producer.join()

                # Data accepted just before a stop waits for the next data object after the restart.
                module.run(self._data(-1))
                received = metrics_registry.get(module.configuration.id).snapshot()["throughput"]["received_total"]
                self.assertTrue(module.recorder.wait_for(received, timeout=20),
                                f"Only {len(module.recorder.values)} of {received} data objects were processed.")
                self.assertEqual(len(module.recorder.values), received)
                self.assertEqual(len(set(module.recorder.values)), received, "A data object was processed twice.")
                self.assertEqual(module.recorder.max_overlap, 1, "Two queue workers processed data at once.")
