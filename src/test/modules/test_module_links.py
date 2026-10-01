"""
How a module forwards data to the modules it is linked to (AbstractModule._call_links): a copy to each of them, through
persistent workers or a thread per data object, and only while both the module and the app are running.
"""
import logging
import threading
import unittest
from types import SimpleNamespace

# Internal imports.
import data_layer
import models
from metrics import data_context_map
from modules.base.base import AbstractModule, ModuleWorker
from test.helpers import TIMEOUT, GlobalStateTestCase, Inbox, wait_for


class _Module(AbstractModule):
    pass


class _Target:
    """
    A linked module. Records what it receives, and on which thread.
    """

    def __init__(self, release: threading.Event = None, failing: set = None):
        self.active = True
        self.inbox = Inbox()
        self.running = threading.Event()
        """Set as soon as the first data object arrives."""
        self.threads: dict[int, threading.Thread] = {}
        """The thread each value was received on."""
        self._release = release
        self._failing = failing or set()

    def run(self, data: models.Data):
        self.running.set()
        if self._release is not None:
            self._release.wait(TIMEOUT)
        value = data.fields["value"]
        if value in self._failing:
            raise ValueError("Can not process {0}.".format(value))
        self.threads[value] = threading.current_thread()
        self.inbox.append(data)

    def values(self) -> list:
        return [data.fields["value"] for data in self.inbox.items]


def _data(value: int, measurement: str = "test") -> models.Data:
    return models.Data(measurement=measurement, fields={"value": value})


def _link_threads(source_id: str = "source") -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name.startswith(f"Link_{source_id}_to_")]


class TestCallLinks(GlobalStateTestCase):

    def _source(self, links=("target",), module_id: str = "source", **parameters) -> _Module:
        source = _Module(SimpleNamespace(**{"id": module_id, "module_name": "inputs.test.source_1.variable",
                                            "active": True, "links": list(links), **parameters}))
        data_layer.module_data[module_id] = SimpleNamespace(instance=source, latest_data=None)
        self.addCleanup(source.stop)
        return source

    @staticmethod
    def _target(module_id: str = "target", **kwargs) -> _Target:
        target = _Target(**kwargs)
        data_layer.module_data[module_id] = SimpleNamespace(instance=target, latest_data=None)
        return target

    def _assert_nothing_forwarded(self, source: _Module):
        self.assertEqual(source._workers, {"target": []}, "Workers were created for the data object.")
        self.assertIsNone(data_layer.module_data[source.configuration.id].latest_data)

    def test_each_linked_module_gets_a_copy_of_its_own(self):
        first, second = self._target("first"), self._target("second")
        data = _data(1)

        self._source(links=["first", "second"])._call_links(data)

        self.assertTrue(first.inbox.wait_for(1) and second.inbox.wait_for(1))
        received = [first.inbox.items[0], second.inbox.items[0]]
        self.assertEqual(received, [data, data])
        self.assertTrue(all(copy is not data for copy in received))
        self.assertIsNot(received[0], received[1])

    def test_the_forwarded_data_is_the_latest_data_of_the_module(self):
        self._target()
        data = _data(1)
        self._source()._call_links(data)
        self.assertIs(data_layer.module_data["source"].latest_data, data)

    def test_nothing_is_forwarded_while_the_module_is_inactive(self):
        self._target()
        source = self._source()
        source.active = False
        source._call_links(_data(1))
        self._assert_nothing_forwarded(source)

    def test_nothing_is_forwarded_while_the_app_stops(self):
        self._target()
        source = self._source()
        data_layer.running = False
        source._call_links(_data(1))
        self._assert_nothing_forwarded(source)

    def test_data_without_a_measurement_is_not_forwarded(self):
        self._target()
        source = self._source()
        for measurement in ("", "   "):
            source._call_links(_data(1, measurement=measurement))
        self._assert_nothing_forwarded(source)

    def test_a_module_which_was_removed_forwards_nothing(self):
        """
        A thread outliving the stop of its module can not be killed, but it must not feed data into a configuration
        the module no longer belongs to.
        """
        self._target()
        source = self._source()
        del data_layer.module_data["source"]
        with self.assertLogs(source.logger, level="ERROR"):
            source._call_links(_data(1))
        self.assertEqual(source._workers, {"target": []})

    def test_a_module_replaced_by_a_newer_instance_forwards_nothing(self):
        self._target()
        source = self._source()
        data_layer.module_data["source"].instance = _Module(source.configuration)
        source._call_links(_data(1))
        self.assertEqual(source._workers, {"target": []})

    def test_the_data_is_distributed_round_robin_between_the_workers_of_a_link(self):
        target = self._target()
        source = self._source(worker_count_per_link=3)

        for value in range(6):
            source._call_links(_data(value))

        self.assertTrue(target.inbox.wait_for(6))
        self.assertEqual(len(source._workers["target"]), 3)
        self.assertEqual(len({target.threads[value] for value in range(6)}), 3)
        for value in range(3):
            self.assertIs(target.threads[value], target.threads[value + 3])
        self.assertEqual({thread.name for thread in target.threads.values()}, {"Link_source_to_target"})

    def test_in_spawn_mode_every_data_object_gets_a_thread_of_its_own(self):
        target = self._target()
        source = self._source(worker_count_per_link=0)

        for value in range(3):
            source._call_links(_data(value))

        self.assertTrue(target.inbox.wait_for(3))
        self.assertEqual(source._workers, {"target": []}, "Spawn mode created persistent workers.")
        self.assertEqual({thread.name for thread in target.threads.values()}, {"Link_source_to_target"})
        self.assertEqual(len(set(target.threads.values())), 3)

    def test_in_spawn_mode_a_link_to_a_module_which_is_gone_is_reported(self):
        source = self._source(links=["missing"], worker_count_per_link=0)
        with self.assertLogs(source.logger, level="ERROR") as logs:
            source._call_links(_data(1))
        self.assertIn("Could not find linked module 'missing'", logs.output[-1])

    def test_a_worker_is_stopped_once_it_worked_off_what_it_has(self):
        target = self._target()
        worker = ModuleWorker(configuration_id="source", module_id="target", logger=logging.getLogger("test"))
        worker.submit(_data(1))

        self.assertTrue(worker.stop(timeout=TIMEOUT))

        self.assertEqual(target.values(), [1])
        self.assertFalse(worker.thread.is_alive())

    def test_only_the_latest_data_is_forwarded_if_asked(self):
        release = threading.Event()
        self.addCleanup(release.set)
        target = self._target(release=release)
        source = self._source(forward_latest_data_only=True)

        source._call_links(_data(0))
        self.assertTrue(target.running.wait(TIMEOUT), "The first data object did not arrive.")
        for value in (1, 2, 3):
            source._call_links(_data(value))
        release.set()

        self.assertTrue(target.inbox.wait_for(2))
        self.assertFalse(target.inbox.wait_for(3, timeout=0.2))
        self.assertEqual(target.values(), [0, 3])

    def test_a_link_added_while_the_module_runs_gets_a_worker(self):
        first, second = self._target("first"), self._target("second")
        source = self._source(links=["first"])
        source._call_links(_data(0))

        source.configuration.links = ["first", "second"]
        source._call_links(_data(1))

        self.assertTrue(first.inbox.wait_for(2) and second.inbox.wait_for(1))
        self.assertEqual((first.values(), second.values()), ([0, 1], [1]))

    def test_a_link_removed_while_the_module_runs_is_stopped(self):
        first, second = self._target("first"), self._target("second")
        source = self._source(links=["first", "second"])
        source._call_links(_data(0))
        self.assertTrue(second.inbox.wait_for(1))

        source.configuration.links = ["first"]
        source._call_links(_data(1))

        self.assertTrue(first.inbox.wait_for(2))
        self.assertEqual(second.values(), [0])
        self.assertNotIn("second", source._workers)
        self.assertTrue(wait_for(lambda: all(thread.name != "Link_source_to_second" for thread in _link_threads())))

    def test_an_inactive_linked_module_is_skipped(self):
        target = self._target()
        target.active = False
        source = self._source()

        source._call_links(_data(0))
        # Whether the linked module is active is checked when the worker gets to the data object.
        (worker,) = source._workers["target"]
        worker.queue.join()
        target.active = True
        source._call_links(_data(1))

        self.assertTrue(target.inbox.wait_for(1))
        self.assertFalse(target.inbox.wait_for(2, timeout=0.2))
        self.assertEqual(target.values(), [1])

    def test_an_error_of_a_linked_module_does_not_stop_its_worker(self):
        target = self._target(failing={0})
        source = self._source()

        with self.assertLogs(source.logger, level="ERROR") as logs:
            source._call_links(_data(0))
            source._call_links(_data(1))
            self.assertTrue(target.inbox.wait_for(1))

        self.assertEqual(target.values(), [1])
        self.assertIn("Can not process 0.", logs.output[0])

    def test_the_flow_is_handed_on_from_module_to_module(self):
        middle, target = _Target(), self._target()
        data_layer.module_data["middle"] = SimpleNamespace(instance=middle, latest_data=None)
        source = self._source(links=["middle"])
        hop = self._source(links=["target"], module_id="hop")

        source._call_links(_data(1))
        self.assertTrue(middle.inbox.wait_for(1))
        first_copy = middle.inbox.items[0]
        hop._call_links(first_copy)
        self.assertTrue(target.inbox.wait_for(1))

        first, second = data_context_map.get(first_copy), data_context_map.get(target.inbox.items[0])
        self.assertEqual((first.source_id, first.visited), ("source", frozenset({"source"})))
        self.assertEqual((second.source_id, second.visited), ("source", frozenset({"source", "hop"})))
        self.assertEqual(second.pipeline_ts, first.pipeline_ts, "The flow is timed from where it started.")


if __name__ == '__main__':
    unittest.main()
