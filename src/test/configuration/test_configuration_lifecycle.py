"""
Running a configuration: the order modules are started and stopped in, data flowing through a pipeline, starting and
stopping single modules, and changing the configuration while it runs.
"""
import asyncio
import json
import threading
import unittest
from unittest import mock

# Internal imports.
import configuration as configuration_module
import data_layer
from configuration import Configuration
from metrics import metrics_registry
from test.helpers import (TIMEOUT, AppTestCase, Client, Collector, GlobalStateTestCase, instance, module_config,
                          wait_for)

PIPELINE: list[dict] = [
    module_config("client", "inputs.test.client_1", host="plc-7"),
    module_config("tag", "inputs.test.client_1.tag", input_module="client", is_tag=True, is_field=False,
                  links=["multiplier"]),
    module_config("source", "inputs.test.source_1.variable", links=["tag"]),
    module_config("multiplier", "processors.test.multiplier_1", links=["collector"]),
    module_config("collector", "outputs.test.collector_1"),
]
"""A source whose data is tagged with the host of a client, multiplied and stored."""


def _created(create_module: mock.Mock) -> list[str]:
    """
    :param create_module: The mock standing in for Configuration._create_module.
    :returns: The ids of the modules it was asked to create, in order.
    """
    return [(call.kwargs.get("module_config") or call.args[0]).id for call in create_module.call_args_list]


class TestStartAndStopOrder(AppTestCase):
    """
    Modules are started from the end of a pipeline to its beginning, so nothing produces data before the modules it
    is sent to exist - and stopped the other way round.
    """

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()

    def test_modules_are_created_in_the_order_of_their_types(self):
        content = [module_config("source", "inputs.test.source_1.variable", links=["tag"]),
                   module_config("tag", "inputs.test.client_1.tag", input_module="client", links=["multiplier"]),
                   module_config("client", "inputs.test.client_1"),
                   module_config("multiplier", "processors.test.multiplier_1", links=["collector"]),
                   module_config("collector", "outputs.test.collector_1", buffered=True),
                   module_config("buffer", "outputs.test.buffer_1", is_buffer=True)]

        with mock.patch.object(Configuration, "_create_module") as create_module:
            self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(content)), {})

        self.assertEqual(_created(create_module), ["buffer", "collector", "multiplier", "client", "tag", "source"])

    def test_a_higher_start_priority_starts_first_within_a_type(self):
        content = [module_config("low", "outputs.test.collector_1", start_priority=1),
                   module_config("default", "outputs.test.collector_1"),
                   module_config("high", "outputs.test.collector_1", start_priority=5),
                   module_config("source", "inputs.test.source_1.variable", start_priority=9,
                                 links=["low", "default", "high"])]

        with mock.patch.object(Configuration, "_create_module") as create_module:
            self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(content)), {})

        self.assertEqual(_created(create_module), ["high", "low", "default", "source"],
                         "Outputs before inputs, whatever their priority.")

    def test_modules_are_stopped_in_the_reverse_order_of_their_types(self):
        self.configuration.load_configuration_from_stream(json.dumps(PIPELINE))

        with mock.patch.object(Configuration, "_spawn_stop_threads",
                               wraps=Configuration._spawn_stop_threads) as spawn_stop_threads:
            self.configuration.stop()

        self.assertEqual([list(call.args[0]) for call in spawn_stop_threads.call_args_list],
                         [["source"], ["tag"], ["client"], ["multiplier"], ["collector"]])


class TestPipeline(AppTestCase):
    """
    Data produced by a variable module passes every module it is linked to, in order.
    """

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()

    def _load(self, content: list[dict]):
        self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(content)), {})

    def test_data_flows_from_the_source_to_the_output(self):
        self._load(PIPELINE)

        instance("source").emit(value=21)

        collector = instance("collector")
        self.assertTrue(collector.inbox.wait_for(1), "Nothing arrived at the output.")
        (data,) = collector.inbox.items
        self.assertEqual((data.measurement, data.fields, data.tags), ("test", {"value": 42}, {"host": "plc-7"}))

    def test_every_module_sees_its_own_copy(self):
        content = [module_config("source", "inputs.test.source_1.variable", links=["multiplier", "collector"]),
                   module_config("multiplier", "processors.test.multiplier_1", links=["doubled"]),
                   module_config("collector", "outputs.test.collector_1"),
                   module_config("doubled", "outputs.test.collector_1")]
        self._load(content)

        emitted = instance("source").emit(value=1)

        self.assertTrue(instance("doubled").inbox.wait_for(1))
        self.assertTrue(instance("collector").inbox.wait_for(1))
        self.assertEqual(instance("doubled").inbox.items[0].fields, {"value": 2})
        self.assertEqual(instance("collector").inbox.items[0].fields, {"value": 1},
                         "One branch changed the data of the other.")
        self.assertEqual(emitted.fields, {"value": 1})

    def test_the_flow_is_measured_from_the_source_to_the_output(self):
        self._load(PIPELINE)

        instance("source").emit(value=1)

        self.assertTrue(wait_for(lambda: "source->collector" in metrics_registry.snapshot()["flows"]))
        self.assertEqual(list(metrics_registry.snapshot()["flows"]), ["source->collector"])
        self.assertTrue(wait_for(lambda: metrics_registry.get("collector").snapshot()["throughput"]
                                 ["processed_total"] == 1))
        for module_id in ("source", "tag", "multiplier", "collector"):
            with self.subTest(module=module_id):
                throughput = metrics_registry.get(module_id).snapshot()["throughput"]
                self.assertEqual((throughput["received_total"], throughput["processed_total"]), (1, 1))

    def test_a_dynamic_variable_reads_the_latest_data_of_another_module(self):
        content = [module_config("source", "inputs.test.source_1.variable", links=["multiplier"]),
                   module_config("multiplier", "processors.test.multiplier_1", factor="${source.factor}",
                                 links=["collector"]),
                   module_config("collector", "outputs.test.collector_1")]
        self._load(content)

        instance("source").emit(value=2, factor=5)

        self.assertTrue(instance("collector").inbox.wait_for(1))
        self.assertEqual(instance("collector").inbox.items[0].fields["value"], 10)

    def test_a_variable_module_uses_the_connection_of_its_input_module(self):
        content = [module_config("client", "inputs.test.client_1", host="plc-9"),
                   module_config("variable", "inputs.test.client_1.variable", input_module="client",
                                 links=["collector"]),
                   module_config("collector", "outputs.test.collector_1")]
        self._load(content)
        variable = instance("variable")
        self.assertIs(variable.input_module_instance, instance("client"))
        self.assertTrue(wait_for(variable.started.is_set))

        variable.emit(value=1)

        self.assertTrue(instance("collector").inbox.wait_for(1))
        self.assertEqual(instance("collector").inbox.items[0].tags, {"host": "plc-9"})

    def test_stopping_ends_every_module(self):
        self._load(PIPELINE)
        instance("source").emit(value=1)
        self.assertTrue(instance("collector").inbox.wait_for(1))
        modules = {module_id: entry.instance for module_id, entry in data_layer.module_data.items()}

        self.configuration.stop()

        self.assertEqual(data_layer.module_data, {})
        for module_id, module in modules.items():
            with self.subTest(module=module_id):
                self.assertFalse(module.active)
                self.assertFalse(module.started.is_set())
        self.assertIsNone(modules["client"].connection, "The stop routine of the client did not run.")
        self.assertTrue(wait_for(lambda: Configuration._alive_module_threads(list(modules)) == []),
                        "A thread of a module outlived the stop routine.")

    def test_the_buffer_module_is_known_while_it_runs(self):
        self._load([module_config("buffer", "outputs.test.buffer_1", is_buffer=True),
                    module_config("collector", "outputs.test.collector_1", buffered=True)])
        self.assertIs(data_layer.buffer_instance, instance("buffer"))

        self.configuration.stop()

        self.assertIsNone(data_layer.buffer_instance)


class TestStartAndStopModule(AppTestCase):
    """
    Configuration.start_module and stop_module: one module at a time, while the others keep running.
    """

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()

    def _load(self, content: list[dict] = None):
        content = content or [module_config("client", "inputs.test.client_1"),
                              module_config("source", "inputs.test.source_1.variable", links=["collector"]),
                              module_config("collector", "outputs.test.collector_1")]
        self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(content)), {})

    def test_a_stopped_module_keeps_its_place_in_the_configuration(self):
        self._load()
        collector = instance("collector")

        self.assertEqual(self.configuration.stop_module("collector"), {})

        self.assertFalse(collector.active)
        self.assertIs(instance("collector"), collector)
        self.assertIn("collector", [module["id"] for module in self.configuration.configuration_dict])
        self.assertTrue(instance("source").active, "Another module was stopped as well.")

    def test_stopping_an_unknown_module_is_no_error(self):
        with self.assertLogs("collectu.configuration", level="WARNING"):
            self.assertEqual(self.configuration.stop_module("unknown"), {})

    def test_a_stop_routine_which_does_not_return_is_reported(self):
        release = threading.Event()

        class Stuck(Collector):
            def stop(self):
                release.wait(TIMEOUT)

        data_layer.registered_modules["outputs.test.collector_1"] = Stuck
        self._load()
        self.addCleanup(release.set)
        self.patch_config(STOP_TIMEOUT=0.2)

        with self.assertLogs("collectu.configuration", level="ERROR"):
            errors = self.configuration.stop_module("collector")

        self.assertEqual(errors, {"collector": ["Could not stop module within time."]})

    def test_a_stopped_module_is_started_again_in_place(self):
        self._load()
        client = instance("client")
        self.assertTrue(wait_for(client.started.is_set))
        self.configuration.stop_module("client")
        self.assertIsNone(client.connection)

        self.assertEqual(self.configuration.start_module(module_id="client"), {})

        self.assertIs(instance("client"), client)
        self.assertTrue(client.active)
        self.assertTrue(wait_for(lambda: client.started.is_set() and client.start_calls == 2))
        self.assertEqual(client.connection, {"host": "localhost"})

    def test_a_module_whose_previous_start_still_runs_is_not_started_twice(self):
        release = threading.Event()

        class Slow(Client):
            def start(self):
                super().start()
                release.wait(TIMEOUT)

        data_layer.registered_modules["inputs.test.client_1"] = Slow
        self._load()
        self.addCleanup(release.set)
        self.assertTrue(wait_for(lambda: instance("client").start_calls == 1))
        with self.assertLogs("collectu.configuration", level="WARNING"):
            self.configuration.stop_module("client")

        with self.assertLogs("collectu.configuration", level="ERROR"):
            errors = self.configuration.start_module(module_id="client")

        self.assertEqual(errors, {"client": ["The previous start routine of the module is still running. "
                                             "Please try again."]})
        self.assertEqual(instance("client").start_calls, 1)

    def test_a_module_is_restarted_while_one_whose_id_begins_with_its_id_still_starts(self):
        release = threading.Event()

        class Slow(Client):
            def start(self):
                super().start()
                if self.configuration.id == "client_10":
                    release.wait(TIMEOUT)

        data_layer.registered_modules["inputs.test.client_1"] = Slow
        self._load([module_config("client_1", "inputs.test.client_1"),
                    module_config("client_10", "inputs.test.client_1")])
        self.addCleanup(release.set)
        client = instance("client_1")
        # The start routine of client_1 has ended, the one of client_10 still runs.
        self.assertTrue(wait_for(lambda: client.started.is_set() and instance("client_10").start_calls == 1 and
                                 "Start_client_1" not in [thread.name for thread in threading.enumerate()]))
        with self.assertNoLogs("collectu.configuration", level="WARNING"):
            self.assertEqual(self.configuration.stop_module("client_1"), {})

        self.assertEqual(self.configuration.start_module(module_id="client_1"), {})

        self.assertTrue(wait_for(lambda: client.started.is_set() and client.start_calls == 2))

    def test_a_module_is_restarted_with_a_new_configuration(self):
        self._load()
        collector = instance("collector")
        changed = module_config("collector", "outputs.test.collector_1", name="renamed")

        self.assertEqual(self.configuration.start_module(module_config=changed), {})

        self.assertIsNot(instance("collector"), collector)
        self.assertFalse(collector.active)
        self.assertEqual(instance("collector").configuration.name, "renamed")
        self.assertIn(changed, self.configuration.configuration_dict)
        # The links of the other modules lead to the new instance.
        instance("source").emit(value=1)
        self.assertTrue(instance("collector").inbox.wait_for(1))

    def test_the_given_id_wins_over_the_one_in_the_configuration(self):
        self._load()
        changed = module_config("whatever", "outputs.test.collector_1", name="renamed")

        self.assertEqual(self.configuration.start_module(module_id="collector", module_config=changed), {})

        self.assertEqual(instance("collector").configuration.name, "renamed")
        self.assertNotIn("whatever", data_layer.module_data)

    def test_a_new_module_is_added_and_started(self):
        self._load()

        self.assertEqual(self.configuration.start_module(
            module_config=module_config("second", "outputs.test.collector_1")), {})

        self.assertTrue(wait_for(lambda: instance("second").started.is_set()))
        self.assertEqual(len(self.configuration.configuration_dict), 4)

    def test_an_invalid_module_configuration_is_refused(self):
        self._load()
        collector = instance("collector")

        errors = self.configuration.start_module(
            module_config=module_config("collector", "outputs.test.collector_1", panel="panel-9"))

        self.assertIn("'panel'", errors["collector"][0])
        self.assertIs(instance("collector"), collector)
        self.assertTrue(collector.active)

    def test_a_module_is_named_by_an_id(self):
        self._load()
        self.assertEqual(self.configuration.start_module(),
                         {"-": ["Either module_id or module_config must be provided."]})
        self.assertEqual(self.configuration.start_module(module_config={"module_name": "outputs.test.collector_1"}),
                         {"-": ["module_config must contain an 'id' field."]})
        self.assertEqual(self.configuration.start_module(module_id="unknown"),
                         {"unknown": ["Module 'unknown' does not exist. Please provide a module_config to start it."]})


class TestChangingTheRunningConfiguration(AppTestCase):
    """
    Adding, removing and replacing modules while the others keep running.
    """

    INITIAL: list[dict] = [module_config("source", "inputs.test.source_1.variable", links=["collector"]),
                           module_config("collector", "outputs.test.collector_1"),
                           module_config("spare", "outputs.test.collector_1")]

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()
        self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(self.INITIAL)), {})

    def test_modules_are_added(self):
        source = instance("source")

        errors = self.configuration.add_modules_to_configuration(
            json.dumps([module_config("added", "outputs.test.collector_1")]))

        self.assertEqual(errors, {})
        self.assertTrue(wait_for(lambda: instance("added").started.is_set()))
        self.assertIs(instance("source"), source, "A running module was restarted.")
        self.assertEqual(self.configuration.configuration_dict[-1]["id"], "added")

    def test_an_invalid_module_is_not_added(self):
        errors = self.configuration.add_modules_to_configuration(
            json.dumps([module_config("source", "outputs.test.collector_1")]))

        self.assertIn("The module id is not unique.", errors["source"])
        self.assertEqual(self.configuration.configuration_dict, self.INITIAL)

    def test_content_which_is_not_a_configuration_is_not_added(self):
        errors = self.configuration.add_modules_to_configuration("{'not': 'a list'")
        self.assertEqual(list(errors), ["-"])
        self.assertEqual(self.configuration.configuration_dict, self.INITIAL)

    def test_modules_are_removed(self):
        spare = instance("spare")

        self.assertEqual(self.configuration.remove_modules_from_configuration(["spare", "unknown"]), {})

        self.assertNotIn("spare", data_layer.module_data)
        self.assertTrue(wait_for(lambda: not spare.active))
        self.assertEqual(self.configuration.configuration_dict, self.INITIAL[:2])

    def test_a_module_others_link_to_is_not_removed(self):
        errors = self.configuration.remove_modules_from_configuration(["collector"])

        self.assertEqual(errors, {"source": ["A linked module with the id 'collector' does not exist."]})
        self.assertTrue(instance("collector").active)
        self.assertEqual(self.configuration.configuration_dict, self.INITIAL)

    def test_removing_the_buffer_forgets_it(self):
        self.configuration.add_modules_to_configuration(
            json.dumps([module_config("buffer", "outputs.test.buffer_1", is_buffer=True)]))
        self.assertIs(data_layer.buffer_instance, instance("buffer"))

        self.assertEqual(self.configuration.remove_modules_from_configuration(["buffer"]), {})

        self.assertIsNone(data_layer.buffer_instance)

    def test_an_update_restarts_changed_modules_and_keeps_the_others(self):
        collector, spare = instance("collector"), instance("spare")
        updated = [dict(self.INITIAL[0], measurement="pressure"),
                   self.INITIAL[1],
                   module_config("added", "outputs.test.collector_1")]

        self.assertEqual(self.configuration.update_configuration(json.dumps(updated)), {})

        self.assertEqual(instance("source").configuration.measurement, "pressure")
        self.assertIs(instance("collector"), collector, "An unchanged module was restarted.")
        self.assertNotIn("spare", data_layer.module_data)
        self.assertTrue(wait_for(lambda: not spare.active))
        self.assertIn("added", data_layer.module_data)
        instance("source").emit(value=1)
        self.assertTrue(collector.inbox.wait_for(1))
        self.assertEqual(collector.inbox.items[0].measurement, "pressure")

    def test_an_invalid_update_changes_nothing(self):
        modules = dict(data_layer.module_data)

        errors = self.configuration.update_configuration(json.dumps([dict(self.INITIAL[0], links=["missing"])]))

        self.assertIn("source", errors)
        self.assertEqual(data_layer.module_data, modules)
        self.assertEqual(self.configuration.configuration_dict, self.INITIAL)


class TestStartRoutine(AppTestCase):
    """
    Configuration._start_module: a module is started in a thread of its own, retried until its start succeeds, and
    a tag or variable module only once its input module is ready.
    """

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()

    def _load(self, content: list[dict]):
        self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(content)), {})

    def test_a_module_which_can_not_be_created_does_not_stop_the_others(self):
        class Broken(Collector):
            def __init__(self, configuration):
                raise RuntimeError("The driver is missing.")

        data_layer.registered_modules["outputs.test.broken_1"] = Broken
        with self.assertLogs("collectu.configuration", level="CRITICAL") as logs:
            self._load([module_config("broken", "outputs.test.broken_1"),
                        module_config("collector", "outputs.test.collector_1")])

        self.assertIn("The driver is missing.", logs.output[0])
        self.assertEqual(list(data_layer.module_data), ["collector"])
        self.assertTrue(wait_for(instance("collector").started.is_set))

    def test_a_module_whose_requirements_can_not_be_imported_is_reported(self):
        class Unimportable(Collector):
            def __init__(self, configuration):
                raise ImportError("No module named 'pyodbc'")

        data_layer.registered_modules["outputs.test.collector_1"] = Unimportable
        with self.assertLogs("collectu.configuration", level="CRITICAL") as logs:
            self._load([module_config("collector", "outputs.test.collector_1")])
        self.assertIn("Import of third party packages failed.", logs.output[0])
        self.assertEqual(data_layer.module_data, {})

    def test_a_deprecated_module_is_reported_when_it_is_started(self):
        class Deprecated(Collector):
            deprecated = True

        data_layer.registered_modules["outputs.test.collector_1"] = Deprecated
        with self.assertLogs("collectu.configuration", level="WARNING") as logs:
            self._load([module_config("collector", "outputs.test.collector_1")])
        self.assertIn("is deprecated", logs.output[0])

    def test_a_module_whose_stop_fails_is_stopped_anyway(self):
        class Failing(Collector):
            def stop(self):
                raise ConnectionError("Already disconnected.")

        data_layer.registered_modules["outputs.test.collector_1"] = Failing
        self._load([module_config("collector", "outputs.test.collector_1")])
        collector = instance("collector")

        with self.assertLogs("collectu.configuration", level="ERROR") as logs:
            self.configuration.stop()

        self.assertIn("Already disconnected.", "\n".join(logs.output))
        self.assertFalse(collector.active)
        self.assertEqual(data_layer.module_data, {})

    def test_dashboard_modules_are_forgotten_with_their_module(self):
        self._load([module_config("collector", "outputs.test.collector_1"),
                    module_config("spare", "outputs.test.collector_1")])
        data_layer.dashboard_modules.append(instance("spare"))

        self.assertEqual(self.configuration.remove_modules_from_configuration(["spare"]), {})

        self.assertEqual(data_layer.dashboard_modules, [])

    def test_a_failing_start_is_retried_until_it_succeeds(self):
        class Flaky(Client):
            def start(self):
                super().start()
                if self.start_calls < 3:
                    raise ConnectionError("Connection refused.")

        data_layer.registered_modules["inputs.test.client_1"] = Flaky
        with self.assertLogs("collectu.configuration", level="ERROR") as logs:
            self._load([module_config("client", "inputs.test.client_1")])
            self.assertTrue(wait_for(instance("client").started.is_set))

        self.assertEqual(instance("client").start_calls, 3)
        self.assertIn("Connection refused.", logs.output[0])

    def test_an_inactive_module_is_not_started(self):
        self._load([module_config("client", "inputs.test.client_1", active=False)])

        client = instance("client")
        self.assertTrue(wait_for(lambda: Configuration._alive_module_threads(["client"]) == []))
        self.assertEqual(client.start_calls, 0)
        self.assertFalse(client.started.is_set())

    def test_a_tag_module_starts_once_its_input_module_is_ready(self):
        release = threading.Event()
        self.addCleanup(release.set)

        class Slow(Client):
            def start(self):
                release.wait(TIMEOUT)
                super().start()

        data_layer.registered_modules["inputs.test.client_1"] = Slow
        self._load([module_config("client", "inputs.test.client_1"),
                    module_config("tag", "inputs.test.client_1.tag", input_module="client")])
        tag = instance("tag")

        self.assertFalse(tag.started.wait(0.2), "The tag module was started before its input module.")
        release.set()
        self.assertTrue(wait_for(tag.started.is_set))
        self.assertIsNotNone(instance("client").connection)

    def test_a_tag_module_starts_anyway_when_its_input_module_never_gets_ready(self):
        self.patch_config(START_TIMEOUT=1)
        release = threading.Event()
        self.addCleanup(release.set)

        class Stuck(Client):
            def start(self):
                release.wait(TIMEOUT)

        data_layer.registered_modules["inputs.test.client_1"] = Stuck
        with self.assertLogs("collectu.inputs.test.client_1.tag.tag", level="WARNING") as logs:
            self._load([module_config("client", "inputs.test.client_1"),
                        module_config("tag", "inputs.test.client_1.tag", input_module="client")])
            self.assertTrue(wait_for(instance("tag").started.is_set))
        self.assertIn("did not report to be ready", logs.output[0])


class TestInvoke(unittest.TestCase):
    """
    Configuration._invoke calls the start and stop methods of modules, which may be async.
    """

    def setUp(self):
        # The event loop _invoke keeps for this thread, which the app never closes.
        self.addCleanup(lambda: getattr(configuration_module._thread_local, "event_loop", None) and
                        configuration_module._thread_local.event_loop.close())

    def test_a_method_is_called(self):
        self.assertEqual(Configuration._invoke(lambda value: value * 2, 21), 42)

    def test_an_async_method_is_awaited(self):
        async def double(value):
            await asyncio.sleep(0)
            return value * 2

        self.assertEqual(Configuration._invoke(double, 21), 42)
        self.assertEqual(Configuration._invoke(double, value=2), 4, "The event loop of the thread is reused.")

    def test_an_async_method_is_awaited_from_inside_a_running_event_loop(self):
        async def double(value):
            await asyncio.sleep(0)
            return value * 2

        async def caller():
            return Configuration._invoke(double, 21)

        self.assertEqual(asyncio.run(caller()), 42)

    def test_an_exception_of_an_async_method_is_raised_to_the_caller(self):
        async def fail():
            raise ValueError("Failed.")

        async def caller():
            return Configuration._invoke(fail)

        with self.assertRaises(ValueError):
            Configuration._invoke(fail)
        with self.assertRaises(ValueError):
            asyncio.run(caller())


class TestLeakedThreads(GlobalStateTestCase):
    """
    Python can not kill a thread, so a thread of a module which does not end is reported by name.
    """

    def _thread(self, name: str) -> threading.Thread:
        release = threading.Event()
        thread = threading.Thread(target=release.wait, args=(TIMEOUT,), name=name, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(release.set)
        return thread

    def test_the_threads_of_a_module_are_found_by_their_names(self):
        threads = [self._thread(name) for name in ("Start_m1", "Stop_m1", "Link_m1_to_m2")]
        self._thread("Link_m2_to_m1")
        self._thread("Start_m2")

        self.assertCountEqual(Configuration._alive_module_threads(["m1"]), threads)
        self.assertEqual(Configuration._alive_module_threads([]), [])

    def test_the_threads_of_a_module_whose_id_begins_with_the_id_are_not_found(self):
        for name in ("Start_m10", "Stop_m10", "Link_m10_to_m1"):
            self._thread(name)

        self.assertEqual(Configuration._alive_module_threads(["m1"]), [])
        self.assertEqual(Configuration._report_leaked_threads(module_ids=["m1"], timeout=3), [])

    def test_a_leaked_thread_is_reported(self):
        self.patch_config(EXC_INFO=False)
        self._thread("Start_m1")

        with self.assertLogs("collectu.configuration", level="WARNING") as logs:
            leaked = Configuration._report_leaked_threads(module_ids=["m1"], timeout=3)

        self.assertEqual(leaked, ["Start_m1"])
        self.assertIn("Thread 'Start_m1' did not end within 3 s", logs.output[0])
        self.assertIn("Set the environment variable EXC_INFO", logs.output[-1])

    def test_where_a_leaked_thread_is_stuck_is_reported_with_exc_info(self):
        self.patch_config(EXC_INFO=True)
        self._thread("Start_m1")

        with self.assertLogs("collectu.configuration", level="WARNING") as logs:
            Configuration._report_leaked_threads(module_ids=["m1"], timeout=3)

        self.assertEqual(len(logs.output), 1)
        self.assertIn("It is currently at:", logs.output[0])
        self.assertIn("wait", logs.output[0])

    def test_nothing_is_reported_without_a_leaked_thread(self):
        self.assertEqual(Configuration._report_leaked_threads(module_ids=["m1"], timeout=3), [])


class TestStopWithAModuleWhichDoesNotStop(AppTestCase):
    """
    A stop routine which does not return can not hold up the stop of the configuration.
    """

    def test_the_configuration_is_stopped_anyway(self):
        release = threading.Event()

        class Stuck(Collector):
            def stop(self):
                release.wait(TIMEOUT)

        data_layer.registered_modules["outputs.test.collector_1"] = Stuck
        configuration = self.create_configuration()
        configuration.load_configuration_from_stream(json.dumps(
            [module_config("collector", "outputs.test.collector_1"),
             module_config("other", "outputs.test.buffer_1")]))
        self.addCleanup(release.set)
        self.patch_config(STOP_TIMEOUT=0.3)

        with self.assertLogs("collectu.configuration", level="ERROR") as logs:
            configuration.stop()

        self.assertIn("did not return within 0.3 s: collector.", "\n".join(logs.output))
        self.assertEqual(data_layer.module_data, {})


if __name__ == '__main__':
    unittest.main()
