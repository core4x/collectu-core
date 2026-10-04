"""
What each type of module does with a data object: a tag module enriches it, a processor transforms it and an output
module stores it - each only once it is ready, and counting what happened in its metrics. And what all of them have
in common: waiting for readiness, stopping their link workers, and installing their third-party requirements.
"""
import asyncio
import concurrent.futures
import threading
import time
import unittest
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, Optional
from unittest import mock

# Internal imports.
import data_layer
import models
import modules.base.base
import utils.plugin_interface
from metrics import metrics_registry, data_context_map, _DataContext
from modules.base.base import AbstractModule
from modules.base.inputs.base import AbstractInputModule, AbstractTagModule, AbstractVariableModule
from modules.base.outputs.base import AbstractOutputModule
from modules.base.processors.base import AbstractProcessorModule
from test.helpers import TIMEOUT, Buffer, GlobalStateTestCase, Inbox, wait_for


def _data(value=1, measurement: str = "test", **tags) -> models.Data:
    return models.Data(measurement=measurement, fields={"value": value}, tags=dict(tags))


def _context(source_id: str = "source") -> _DataContext:
    """A data object's context, as the module forwarding it sets it."""
    now = time.monotonic()
    return _DataContext(pipeline_ts=now, source_id=source_id, link_ts=now, visited=frozenset({source_id}))


def _totals(module_id: str) -> dict[str, int]:
    snapshot = metrics_registry.get(module_id).snapshot()
    return {"received": snapshot["throughput"]["received_total"],
            "processed": snapshot["throughput"]["processed_total"],
            "errors": snapshot["errors"]["error_total"],
            "drops": snapshot["errors"]["drop_total"]}


class _Tag(AbstractTagModule):

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.seen: list = []

    def _run(self) -> dict:
        self.seen.append(self.current_input_data)
        return {"site": "Stuttgart"}


class TestTagModule(GlobalStateTestCase):
    """
    A tag module adds what its _run returns to the fields or the tags of the data object, and forwards it.
    """

    def _tag(self, cls=_Tag, **parameters):
        tag = cls(models.TagModule(id="tag", module_name="inputs.test.client_1.tag", **parameters))
        tag.started.set()
        self.addCleanup(tag._release_event_loop)
        patcher = mock.patch.object(tag, "_call_links")
        self.forwarded = patcher.start()
        self.addCleanup(patcher.stop)
        return tag

    def test_the_values_are_added_to_the_fields(self):
        data = _data(1, unit="bar")
        self._tag().run(data)
        self.assertEqual((data.fields, data.tags), ({"value": 1, "site": "Stuttgart"}, {"unit": "bar"}))
        self.forwarded.assert_called_once_with(data)

    def test_the_values_are_added_to_the_tags(self):
        data = _data(1, unit="bar")
        self._tag(is_tag=True, is_field=False).run(data)
        self.assertEqual((data.fields, data.tags), ({"value": 1}, {"unit": "bar", "site": "Stuttgart"}))

    def test_the_values_are_added_to_both(self):
        data = _data(1)
        self._tag(is_tag=True, is_field=True).run(data)
        self.assertEqual((data.fields, data.tags), ({"value": 1, "site": "Stuttgart"}, {"site": "Stuttgart"}))

    def test_the_existing_fields_are_replaced_if_asked(self):
        data = _data(1, unit="bar")
        self._tag(replace_existing=True).run(data)
        self.assertEqual((data.fields, data.tags), ({"site": "Stuttgart"}, {"unit": "bar"}))

    def test_the_existing_tags_are_replaced_if_asked(self):
        data = _data(1, unit="bar")
        self._tag(replace_existing=True, is_tag=True, is_field=False).run(data)
        self.assertEqual((data.fields, data.tags), ({"value": 1}, {"site": "Stuttgart"}))

    def test_the_data_object_is_available_while_the_module_runs(self):
        tag, data = self._tag(), _data(1)
        tag.run(data)
        self.assertEqual(tag.seen, [data])
        self.assertIsNone(tag.current_input_data)

    def test_an_async_run_is_awaited(self):
        class AsyncTag(_Tag):
            async def _run(self) -> dict:
                await asyncio.sleep(0)
                return {"site": "Berlin"}

        data = _data(1)
        self._tag(AsyncTag).run(data)
        self.assertEqual(data.fields["site"], "Berlin")

    def test_an_inactive_module_does_nothing(self):
        tag = self._tag(active=False)
        tag.run(_data(1))
        self.assertEqual(tag.seen, [])
        self.forwarded.assert_not_called()

    def test_an_error_is_logged_and_counted_and_nothing_is_forwarded(self):
        class Failing(_Tag):
            def _run(self) -> dict:
                raise KeyError("site")

        tag = self._tag(Failing)
        with self.assertLogs(tag.logger, level="ERROR"):
            tag.run(_data(1))
        self.forwarded.assert_not_called()
        self.assertEqual(_totals("tag"), {"received": 1, "processed": 0, "errors": 1, "drops": 0})

    def test_what_was_received_and_processed_is_counted(self):
        tag, data = self._tag(), _data(1)
        data_context_map.set(data, _context())
        tag.run(data)
        self.assertEqual(_totals("tag"), {"received": 1, "processed": 1, "errors": 0, "drops": 0})
        self.assertEqual(metrics_registry.get("tag").snapshot()["link_queue_wait_ms"]["sample_count"], 1)


class _Processor(AbstractProcessorModule):
    field_requirements = ["(key value with int)"]
    tag_requirements = ["(keys == 0)"]

    def __init__(self, configuration, thread_safe: bool = False):
        super().__init__(configuration=configuration, thread_safe=thread_safe)
        self.inbox = Inbox()
        self.threads: set[int] = set()

    def _run(self, data: models.Data) -> models.Data:
        self.threads.add(threading.get_ident())
        self.inbox.append(data.fields["value"])
        data.fields["value"] += 1
        return data


class TestProcessorModule(GlobalStateTestCase):
    """
    A processor transforms the data objects meeting its requirements and forwards what its _run returns.
    """

    def _processor(self, cls=_Processor, **kwargs):
        processor = cls(models.ProcessorModule(id="processor", module_name="processors.test.module_1"), **kwargs)
        processor.started.set()
        self.addCleanup(processor._release_event_loop)
        patcher = mock.patch.object(processor, "_call_links")
        self.forwarded = patcher.start()
        self.addCleanup(patcher.stop)
        return processor

    def test_the_transformed_data_is_forwarded(self):
        data = _data(1)
        self._processor().run(data)
        self.forwarded.assert_called_once_with(data)
        self.assertEqual(data.fields["value"], 2)
        self.assertEqual(_totals("processor"), {"received": 1, "processed": 1, "errors": 0, "drops": 0})

    def test_a_new_data_object_continues_the_flow_of_the_old_one(self):
        class Replacing(_Processor):
            def _run(self, data: models.Data) -> models.Data:
                return models.Data(measurement="replaced", fields={"value": 0})

        data, context = _data(1), _context()
        data_context_map.set(data, context)
        self._processor(Replacing).run(data)
        (replacement,) = self.forwarded.call_args.args
        self.assertEqual(replacement.measurement, "replaced")
        self.assertIs(data_context_map.get(replacement), context)

    def test_data_not_meeting_the_field_requirements_is_not_processed(self):
        processor = self._processor()
        with self.assertLogs(processor.logger, level="ERROR") as logs:
            processor.run(_data("1"))
        self.assertIn("Invalid field input data", logs.output[0])
        self.assertEqual(processor.inbox.items, [])
        self.assertEqual(_totals("processor")["errors"], 1)

    def test_data_not_meeting_the_tag_requirements_is_not_processed(self):
        processor = self._processor()
        with self.assertLogs(processor.logger, level="ERROR") as logs:
            processor.run(_data(1, unit="bar"))
        self.assertIn("Invalid tag input data", logs.output[0])
        self.assertEqual(processor.inbox.items, [])

    def test_data_without_a_measurement_is_not_processed(self):
        processor = self._processor()
        processor.run(_data(1, measurement=""))
        self.assertEqual(processor.inbox.items, [])
        self.forwarded.assert_not_called()

    def test_an_async_run_is_awaited(self):
        class AsyncProcessor(_Processor):
            async def _run(self, data: models.Data) -> models.Data:
                await asyncio.sleep(0)
                data.fields["value"] *= 10
                return data

        data = _data(2)
        self._processor(AsyncProcessor).run(data)
        self.assertEqual(data.fields["value"], 20)

    def test_an_inactive_module_does_nothing(self):
        processor = self._processor()
        processor.active = False
        processor.run(_data(1))
        self.assertEqual(processor.inbox.items, [])
        self.assertIsNone(metrics_registry.get("processor").snapshot()["processing_time_ms"]["mean"])

    def test_an_error_is_logged_and_counted(self):
        class Failing(_Processor):
            def _run(self, data: models.Data) -> models.Data:
                raise ZeroDivisionError("division by zero")

        processor = self._processor(Failing)
        with self.assertLogs(processor.logger, level="ERROR"):
            processor.run(_data(1))
        self.forwarded.assert_not_called()
        self.assertEqual(_totals("processor")["errors"], 1)

    def test_a_thread_safe_processor_works_off_its_queue_in_order_on_one_thread(self):
        processor = self._processor(thread_safe=True)
        self.addCleanup(_deactivate, processor)

        for value in range(20):
            processor.run(_data(value))

        self.assertTrue(processor.inbox.wait_for(20))
        self.assertEqual(processor.inbox.items, list(range(20)))
        self.assertEqual(len(processor.threads), 1)
        self.assertNotIn(threading.get_ident(), processor.threads, "_run was called on the calling thread.")
        self.assertTrue(wait_for(lambda: self.forwarded.call_count == 20))


def _deactivate(module):
    """
    Lets the queue worker of a module leave, which is no daemon thread. It notices within a second and is not waited
    for: it touches nothing a later test uses.
    """
    module.active = False


class _Output(AbstractOutputModule):
    field_requirements = ["(key value with int)"]

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.inbox = Inbox()
        self.failing: set = set()

    def _run(self, data: models.Data):
        if data.fields["value"] in self.failing:
            raise ConnectionError("The database is not reachable.")
        self.inbox.append(data.fields["value"])


class TestOutputModule(GlobalStateTestCase):
    """
    An output module queues the data objects meeting its requirements and stores them on a thread of its own. What
    can not be stored is handed to the buffer module, if there is one.
    """

    def _output(self, ready: bool = True) -> _Output:
        output = _Output(models.OutputModule(id="output", module_name="outputs.test.collector_1"))
        data_layer.module_data["output"] = SimpleNamespace(instance=output, latest_data=None,
                                                           configuration=output.configuration)
        self.addCleanup(_deactivate, output)
        if ready:
            output.started.set()
        return output

    def _buffer(self) -> Buffer:
        buffer = Buffer(models.OutputModule(id="buffer", module_name="outputs.test.buffer_1", is_buffer=True))
        data_layer.buffer_instance = buffer
        return buffer

    def test_data_is_stored_once_the_module_is_ready(self):
        output = self._output(ready=False)
        output.run(_data(1))

        self.assertFalse(output.inbox.wait_for(1, timeout=0.2), "Data was stored before the module was ready.")
        output.started.set()
        self.assertTrue(output.inbox.wait_for(1))
        self.assertTrue(wait_for(lambda: _totals("output")["processed"] == 1))

    def test_the_latest_data_is_kept_in_the_data_layer(self):
        output, data = self._output(), _data(1)
        output.run(data)
        self.assertIs(data_layer.module_data["output"].latest_data, data)

    def test_data_arriving_while_the_module_is_being_removed_is_still_stored(self):
        output = self._output()
        del data_layer.module_data["output"]
        with self.assertLogs(output.logger, level="ERROR"):
            output.run(_data(1))
        self.assertTrue(output.inbox.wait_for(1))

    def test_an_async_run_is_awaited(self):
        class AsyncOutput(_Output):
            async def _run(self, data: models.Data):
                await asyncio.sleep(0)
                self.inbox.append(data.fields["value"] * 10)

        output = AsyncOutput(models.OutputModule(id="output", module_name="outputs.test.collector_1"))
        self.addCleanup(output._release_event_loop)
        self.addCleanup(_deactivate, output)
        output.started.set()
        output.run(_data(1))
        self.assertTrue(output.inbox.wait_for(1))
        self.assertEqual(output.inbox.items, [10])

    def test_data_not_meeting_the_requirements_is_not_stored(self):
        output = self._output()
        with self.assertLogs(output.logger, level="ERROR") as logs:
            output.run(_data("1"))
        self.assertIn("Invalid field input data", logs.output[0])
        self.assertTrue(output.queue.empty())
        self.assertEqual(_totals("output")["errors"], 1)

    def test_data_without_a_measurement_is_not_stored(self):
        output = self._output()
        output.run(_data(1, measurement=""))
        self.assertTrue(output.queue.empty())
        self.assertEqual(_totals("output")["received"], 1)

    def test_an_inactive_module_does_nothing(self):
        output = self._output()
        output.active = False
        output.run(_data(1))
        self.assertTrue(output.queue.empty())
        self.assertIsNone(output._queue_worker._thread)

    def test_a_data_object_which_fails_does_not_stop_the_others(self):
        output = self._output()
        output.failing = {2}
        with self.assertLogs(output.logger, level="ERROR") as logs:
            for value in (1, 2, 3):
                output.run(_data(value))
            self.assertTrue(output.inbox.wait_for(2))
        self.assertEqual(output.inbox.items, [1, 3])
        self.assertIn("The database is not reachable.", logs.output[0])
        self.assertTrue(wait_for(lambda: _totals("output") == {"received": 3, "processed": 2, "errors": 1,
                                                               "drops": 0}))

    def test_the_flow_of_a_data_object_ends_at_the_output(self):
        output, data = self._output(), _data(1)
        data_context_map.set(data, _context("source"))
        output.run(data)
        self.assertTrue(wait_for(lambda: "source->output" in metrics_registry.snapshot()["flows"]))
        self.assertEqual(metrics_registry.get("output").snapshot()["internal_queue_wait_ms"]["sample_count"], 1)

    def test_data_is_buffered_under_the_id_of_the_module(self):
        output, buffer = self._output(), self._buffer()
        first, second = _data(1), _data(2)

        self.assertTrue(output._buffer(first))
        self.assertTrue(output._buffer(second, invalid=True))

        self.assertEqual(dict(buffer.stored), {"output_buffer": [first], "output_bin": [second]})
        self.assertIs(output._get_buffer(), first)
        self.assertIsNone(output._get_buffer(), "Invalid data is never handed back.")

    def test_without_a_buffer_nothing_is_buffered(self):
        output = self._output()
        self.assertFalse(output._buffer(_data(1)))
        self.assertIsNone(output._get_buffer())

    def test_a_failing_buffer_is_reported(self):
        output = self._output()
        data_layer.buffer_instance = mock.Mock(**{"store_buffer_data.side_effect": OSError("Disk full."),
                                                  "get_buffer_data.side_effect": OSError("Disk gone.")})
        with self.assertLogs(output.logger, level="ERROR") as logs:
            self.assertFalse(output._buffer(_data(1)))
            self.assertIsNone(output._get_buffer())
        self.assertEqual(len(logs.output), 2)

    def test_buffered_data_is_stored_before_new_data(self):
        output, buffer = self._output(), self._buffer()
        buffer.stored["output_buffer"] = [_data(1), _data(2)]

        output.run(_data(3))

        self.assertTrue(output.inbox.wait_for(3))
        self.assertEqual(output.inbox.items, [1, 2, 3])

    def test_data_is_buffered_when_the_queue_is_full(self):
        self.patch_config(STOP_LIMIT=2)
        output, buffer = self._output(), self._buffer()

        # Without its queue worker, nothing works the queue off.
        with mock.patch.object(output._queue_worker, "start"):
            for value in (1, 2, 3):
                output.run(_data(value))

        self.assertEqual([data.fields["value"] for data in buffer.stored["output_buffer"]], [3])
        self.assertEqual(_totals("output")["drops"], 0)

    def test_data_is_dropped_when_the_queue_is_full_and_there_is_no_buffer(self):
        self.patch_config(STOP_LIMIT=2)
        output = self._output()

        with mock.patch.object(output._queue_worker, "start"), self.assertLogs(output.logger, level="ERROR"):
            for value in (1, 2, 3, 4):
                output.run(_data(value))

        self.assertEqual(output.queue.qsize(), 2)
        self.assertEqual(_totals("output")["drops"], 2)


class TestInputAndVariableModules(GlobalStateTestCase):
    """
    Input and variable modules drive themselves, so what they forward is counted where they forward it.
    """

    def _modules(self):
        for cls, module_id in ((AbstractInputModule, "input"), (AbstractVariableModule, "variable")):
            module = cls(SimpleNamespace(id=module_id, module_name="inputs.test.client_1", active=True, links=[]))
            data_layer.module_data[module_id] = SimpleNamespace(instance=module, latest_data=None)
            yield module

    def test_what_is_forwarded_is_counted(self):
        for module in self._modules():
            with self.subTest(module=type(module).__name__):
                module._call_links(_data(1))
                self.assertEqual(_totals(module.configuration.id),
                                 {"received": 1, "processed": 1, "errors": 0, "drops": 0})

    def test_an_error_while_forwarding_is_counted_and_raised(self):
        for module in self._modules():
            with self.subTest(module=type(module).__name__):
                with mock.patch.object(AbstractModule, "_call_links", side_effect=RuntimeError("Broken.")):
                    with self.assertRaises(RuntimeError):
                        module._call_links(_data(1))
                self.assertEqual(_totals(module.configuration.id)["errors"], 1)


class _Module(AbstractModule):
    pass


def _module(module_id: str = "module", **parameters) -> _Module:
    return _Module(SimpleNamespace(**{"id": module_id, "module_name": "processors.test.module_1", "active": True,
                                      **parameters}))


class TestReadiness(GlobalStateTestCase):
    """
    The logic of a module only runs once its start method established what it needs, and a tag or variable module
    only starts once its input module is ready - but neither waits forever.
    """

    def setUp(self):
        super().setUp()
        self.patch_config(START_TIMEOUT=1)

    @staticmethod
    def _later(call):
        timer = threading.Timer(0.1, call)
        timer.start()
        return timer

    def test_a_ready_module_is_not_waited_for(self):
        module = _module()
        module.started.set()
        self.assertTrue(module._await_started())

    def test_a_module_is_waited_for_until_it_is_ready(self):
        module = _module()
        self._later(module.started.set)
        self.assertTrue(module._await_started())

    def test_a_module_which_never_gets_ready_is_waited_for_only_once(self):
        module = _module()
        with self.assertLogs(module.logger, level="WARNING") as logs:
            self.assertFalse(module._await_started())
        self.assertIn("did not report to be ready within 1 s", logs.output[0])

        started = time.monotonic()
        self.assertFalse(module._await_started())
        self.assertLess(time.monotonic() - started, 0.5, "The timeout was waited for a second time.")

        module.started.set()
        self.assertTrue(module._await_started())
        self.assertFalse(module._readiness_timed_out, "A readiness lost later on is not waited for again.")

    def test_a_module_stopped_while_it_is_waited_for_is_not_ready(self):
        # Longer than the second the readiness is waited for at a time, so the stop is noticed before the timeout.
        self.patch_config(START_TIMEOUT=3)
        module = _module()
        self._later(lambda: setattr(module, "active", False))
        with self.assertNoLogs(module.logger, level="WARNING"):
            self.assertFalse(module._await_started())
        self.assertFalse(module._readiness_timed_out)

    def test_a_module_without_an_input_module_does_not_wait(self):
        self.assertTrue(_module()._await_input_module())

    def test_an_input_module_without_readiness_is_not_waited_for(self):
        module = _module()
        module.input_module_instance = SimpleNamespace(active=True)
        self.assertTrue(module._await_input_module())

    def test_the_input_module_is_waited_for_until_it_is_ready(self):
        module, input_module = _module(), _module("input")
        module.input_module_instance = input_module
        self._later(input_module.started.set)
        self.assertTrue(module._await_input_module())

    def test_an_input_module_which_never_gets_ready_is_waited_for_until_the_timeout(self):
        module = _module()
        module.input_module_instance = _module("input")
        with self.assertLogs(module.logger, level="WARNING") as logs:
            self.assertFalse(module._await_input_module())
        self.assertIn("The input module 'input' did not report to be ready within 1 s.", logs.output[0])

    def test_waiting_ends_when_the_input_module_is_stopped(self):
        self.patch_config(START_TIMEOUT=3)
        module, input_module = _module(), _module("input")
        module.input_module_instance = input_module
        self._later(lambda: setattr(input_module, "active", False))
        with self.assertNoLogs(module.logger, level="WARNING"):
            self.assertFalse(module._await_input_module())


class TestStop(GlobalStateTestCase):
    """
    The stop method of every module is wrapped, so the link workers of the module are stopped after it - whatever
    the module's own stop method does.
    """

    def setUp(self):
        super().setUp()
        self.target = Inbox()
        data_layer.module_data["target"] = SimpleNamespace(instance=SimpleNamespace(active=True,
                                                                                    run=self.target.append))

    def _start_forwarding(self, cls) -> AbstractModule:
        module = cls(SimpleNamespace(id="source", module_name="inputs.test.source_1.variable", active=True,
                                     links=["target"]))
        data_layer.module_data["source"] = SimpleNamespace(instance=module, latest_data=None)
        module._call_links(_data(1))
        self.assertTrue(self.target.wait_for(1))
        return module

    def _assert_workers_stopped(self, module: AbstractModule):
        self.assertEqual(module._workers, {"target": []})
        self.assertTrue(wait_for(lambda: not [thread for thread in threading.enumerate()
                                              if thread.name.startswith("Link_source_to_")]))

    def test_the_link_workers_are_stopped_after_the_stop_of_the_module(self):
        workers_during_stop = []

        class Stopping(AbstractModule):
            def stop(self):
                workers_during_stop.append(len(self._workers["target"]))

        module = self._start_forwarding(Stopping)
        module.stop()

        self.assertEqual(workers_during_stop, [1])
        self._assert_workers_stopped(module)

    def test_the_link_workers_are_stopped_even_if_the_stop_of_the_module_raises(self):
        class Failing(AbstractModule):
            def stop(self):
                raise ConnectionError("Already disconnected.")

        module = self._start_forwarding(Failing)
        with self.assertRaises(ConnectionError):
            module.stop()
        self._assert_workers_stopped(module)

    def test_an_async_stop_is_awaited(self):
        stopped = []

        class AsyncStopping(AbstractModule):
            async def stop(self):
                await asyncio.sleep(0)
                stopped.append(True)

        module = self._start_forwarding(AsyncStopping)
        module.stop()

        self.assertEqual(stopped, [True])
        self._assert_workers_stopped(module)

    def test_an_async_stop_is_awaited_when_called_inside_a_running_event_loop(self):
        stopped = []

        class AsyncStopping(AbstractModule):
            async def stop(self):
                await asyncio.sleep(0)
                stopped.append(threading.current_thread())

        module = self._start_forwarding(AsyncStopping)

        async def caller():
            module.stop()

        asyncio.run(caller())

        self.assertEqual(len(stopped), 1)
        self.assertIsNot(stopped[0], threading.current_thread(), "The running event loop was not left alone.")
        self._assert_workers_stopped(module)

    def test_a_module_without_a_stop_of_its_own_stops_its_workers(self):
        module = self._start_forwarding(_Module)
        module.stop()
        self._assert_workers_stopped(module)


def _in_the_background(call: Callable[[], Any]) -> concurrent.futures.Future:
    """
    Calls on a thread of its own, as the runtime calls start, stop and _run on different threads.

    :param call: A callable without arguments.
    :returns: The future of its result.
    """
    future = concurrent.futures.Future()

    def target():
        try:
            future.set_result(call())
        except BaseException as e:
            future.set_exception(e)

    threading.Thread(target=target, daemon=True).start()
    return future


def _on_another_thread(call: Callable[[], Any]) -> Any:
    """
    Calls on a thread of its own and waits for it.

    :param call: A callable without arguments.
    :returns: Its return value. Its exception is raised.
    """
    return _in_the_background(call).result(timeout=TIMEOUT)


def _event_loop_threads(module_id: str) -> list[threading.Thread]:
    """
    :param module_id: The id of the module owning the event loop.
    :returns: The running threads of its event loop.
    """
    return [thread for thread in threading.enumerate() if thread.name == "Loop_{0}".format(module_id)]


class _AsyncClient(_Module):
    """
    A module with an async client, which start creates, _run uses and stop closes - each called by another thread.
    """

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.client: Optional[dict] = None
        self.calls: list[tuple[str, asyncio.AbstractEventLoop, str]] = []
        """The method, the event loop and the thread of each call."""

    def _record(self, method: str):
        self.calls.append((method, asyncio.get_running_loop(), threading.current_thread().name))

    async def start(self):
        self._record("start")
        self.client = {"value": 42}

    async def _run(self, key: str) -> Any:
        self._record("_run")
        await asyncio.sleep(0)
        return self.client[key]

    async def stop(self):
        self._record("stop")
        self.client = None


class TestEventLoop(GlobalStateTestCase):
    """
    All async methods of a module run on one event loop of its own - start, stop and _run alike, whichever thread calls
    them - so a client created by start can be used by _run and closed by stop. The event loop keeps running between
    the calls, and is closed once the module was stopped. A tag or variable module uses the one of its input module.
    """

    def _module(self, cls, module_id: str = "module"):
        module = cls(SimpleNamespace(id=module_id, module_name="processors.test.module_1", active=True))
        # The event loop is closed in the background, so the next test waits for it.
        self.addCleanup(lambda: wait_for(lambda: not _event_loop_threads(module_id)))
        self.addCleanup(module._release_event_loop)
        return module

    def _stop(self, module: AbstractModule):
        """
        Stops the module as the runtime does: it is deactivated before its stop method is called.
        """
        module.active = False
        _on_another_thread(module.stop)

    def test_start_run_and_stop_run_on_one_event_loop_of_the_module(self):
        module = self._module(_AsyncClient)

        _on_another_thread(lambda: module._invoke(module.start))
        self.assertEqual(_on_another_thread(lambda: module._invoke(module._run, "value")), 42)
        self._stop(module)

        self.assertEqual([method for method, _, _ in module.calls], ["start", "_run", "stop"])
        self.assertEqual(len({loop for _, loop, _ in module.calls}), 1, "The methods ran on different event loops.")
        self.assertEqual({thread for _, _, thread in module.calls}, {"Loop_module"})
        self.assertIsNone(module.client)

    def test_a_regular_method_is_called_on_the_calling_thread(self):
        class Regular(_Module):
            def _run(self) -> threading.Thread:
                return threading.current_thread()

        module = self._module(Regular)
        self.assertIs(module._invoke(module._run), threading.current_thread())
        self.assertEqual(_event_loop_threads("module"), [], "An event loop was opened for a regular method.")

    def test_an_exception_of_an_async_method_is_raised_to_the_caller(self):
        class Failing(_Module):
            async def start(self):
                raise ConnectionError("Connection refused.")

        module = self._module(Failing)
        with self.assertRaisesRegex(ConnectionError, "Connection refused."):
            _on_another_thread(lambda: module._invoke(module.start))

    def test_a_task_created_by_start_keeps_running_after_start_returned(self):
        ticks = []

        class Polling(_Module):
            async def start(self):
                async def poll():
                    while True:
                        ticks.append(None)
                        await asyncio.sleep(0.01)

                self.poller = asyncio.create_task(poll())

        module = self._module(Polling)
        _on_another_thread(lambda: module._invoke(module.start))

        self.assertTrue(wait_for(lambda: len(ticks) >= 3), "The task stopped running when start returned.")

    def test_the_tasks_left_running_are_cancelled_and_the_event_loop_is_closed_once_the_module_was_stopped(self):
        cancelled = threading.Event()

        class Polling(_Module):
            async def start(self):
                async def poll():
                    try:
                        await asyncio.sleep(TIMEOUT * 10)
                    except asyncio.CancelledError:
                        cancelled.set()
                        raise

                self.poller = asyncio.create_task(poll())

        module = self._module(Polling)
        _on_another_thread(lambda: module._invoke(module.start))
        self.assertEqual(len(_event_loop_threads("module")), 1)

        self._stop(module)

        self.assertTrue(cancelled.wait(TIMEOUT), "The task was not cancelled.")
        self.assertTrue(wait_for(lambda: not _event_loop_threads("module")), "The event loop was not closed.")

    def test_a_start_method_still_running_when_the_module_is_stopped_may_end_by_itself(self):
        class Blocking(_Module):
            async def start(self):
                self.started.set()
                while self.active:
                    await asyncio.sleep(0.01)
                # Still cleaning up when its stop method already returned.
                await asyncio.sleep(0.1)
                return "ended"

        module = self._module(Blocking)
        start = _in_the_background(lambda: module._invoke(module.start))
        self.assertTrue(module.started.wait(TIMEOUT))

        self._stop(module)

        self.assertEqual(start.result(timeout=TIMEOUT), "ended")
        self.assertTrue(wait_for(lambda: not _event_loop_threads("module")))

    def test_a_start_method_which_ignores_the_stop_is_cancelled_after_the_stop_timeout(self):
        self.patch_config(STOP_TIMEOUT=0.2)

        class Stuck(_Module):
            async def start(self):
                self.started.set()
                await asyncio.sleep(TIMEOUT * 10)

        module = self._module(Stuck)
        start = _in_the_background(lambda: module._invoke(module.start))
        self.assertTrue(module.started.wait(TIMEOUT))

        self._stop(module)

        with self.assertRaises(concurrent.futures.CancelledError):
            start.result(timeout=TIMEOUT)
        self.assertTrue(wait_for(lambda: not _event_loop_threads("module")))

    def test_a_module_restarted_in_place_gets_a_new_event_loop(self):
        module = self._module(_AsyncClient)
        _on_another_thread(lambda: module._invoke(module.start))
        self._stop(module)
        self.assertTrue(wait_for(lambda: not _event_loop_threads("module")))

        module.active = True
        _on_another_thread(lambda: module._invoke(module.start))
        self.assertEqual(_on_another_thread(lambda: module._invoke(module._run, "value")), 42)

        first_start, stop, second_start, run = (loop for _, loop, _ in module.calls)
        self.assertIs(first_start, stop)
        self.assertIs(second_start, run)
        self.assertIsNot(first_start, second_start)

    def test_a_call_of_a_stopped_module_does_not_keep_its_event_loop_open(self):
        module = self._module(_AsyncClient)
        _on_another_thread(lambda: module._invoke(module.start))
        client = module.client
        self._stop(module)
        self.assertTrue(wait_for(lambda: not _event_loop_threads("module")))

        # As the queue worker of an output module does, which picked up one last data object meanwhile.
        module.client = client
        self.assertEqual(module._invoke(module._run, "value"), 42)

        self.assertTrue(wait_for(lambda: not _event_loop_threads("module")), "The event loop was left open.")

    def test_an_async_method_can_not_be_waited_for_on_its_own_event_loop(self):
        class Waiting(_Module):
            async def start(self):
                # Would block the event loop which has to run the coroutine it waits for.
                self._invoke(self._connect)

            async def _connect(self):
                pass

        module = self._module(Waiting)
        with self.assertRaisesRegex(RuntimeError, "Please await the method instead"):
            _on_another_thread(lambda: module._invoke(module.start))

    def test_a_tag_module_uses_the_event_loop_of_its_input_module(self):
        class Input(_Module):
            async def start(self):
                self.loop = asyncio.get_running_loop()

        class Tag(_Module):
            async def _run(self) -> asyncio.AbstractEventLoop:
                return asyncio.get_running_loop()

        input_module, tag = self._module(Input, "input"), self._module(Tag, "tag")
        tag.input_module_instance = input_module
        _on_another_thread(lambda: input_module._invoke(input_module.start))

        self.assertIs(_on_another_thread(lambda: tag._invoke(tag._run)), input_module.loop)
        self.assertEqual(_event_loop_threads("tag"), [])

    def test_a_shared_event_loop_is_closed_once_the_input_module_and_its_tag_module_were_stopped(self):
        class Input(_Module):
            async def start(self):
                self.loop = asyncio.get_running_loop()

        class Tag(_Module):
            async def _run(self) -> asyncio.AbstractEventLoop:
                return asyncio.get_running_loop()

        input_module, tag = self._module(Input, "input"), self._module(Tag, "tag")
        tag.input_module_instance = input_module
        _on_another_thread(lambda: input_module._invoke(input_module.start))
        _on_another_thread(lambda: tag._invoke(tag._run))

        self._stop(input_module)
        self.assertIs(_on_another_thread(lambda: tag._invoke(tag._run)), input_module.loop,
                      "The event loop was closed while the tag module still used it.")
        self.assertEqual(len(_event_loop_threads("input")), 1)

        self._stop(tag)
        self.assertTrue(wait_for(lambda: not _event_loop_threads("input")))


class TestThirdPartyRequirements(GlobalStateTestCase):
    """
    A module installs its missing third-party requirements when it is created, and can not be created without them.
    """

    class _Needy(AbstractModule):
        third_party_requirements = ["collectu-test-package==1.0"]

    def _create(self, installed: bool):
        with mock.patch.object(utils.plugin_interface, "requirement_is_installed",
                               return_value=(installed, "Requirement 'collectu-test-package' is not installed.")), \
                mock.patch.object(utils.plugin_interface, "install_plugin_requirement", return_value=0) as install:
            module = self._Needy(SimpleNamespace(id="module", module_name="processors.test.module_1", active=True))
        return module, install

    def test_a_missing_requirement_is_installed(self):
        with self.assertLogs("collectu.processors.test.module_1.module", level="WARNING"):
            _, install = self._create(installed=False)
        install.assert_called_once_with("collectu-test-package==1.0")

    def test_an_installed_requirement_is_not_installed_again(self):
        _, install = self._create(installed=True)
        install.assert_not_called()

    def test_a_module_whose_requirements_can_not_be_imported_is_not_created(self):
        class Unimportable(self._Needy):
            @classmethod
            def import_third_party_requirements(cls) -> bool:
                raise ImportError("No module named 'collectu_test_package'")

        self._Needy = Unimportable
        with self.assertLogs("collectu.processors.test.module_1.module", level="CRITICAL"):
            with self.assertRaises(ImportError):
                self._create(installed=True)


if __name__ == '__main__':
    unittest.main()
