"""
Reporting to the hub and to other motherships, and executing the tasks they hand out (utils.mothership_interface).

The reporting and requesting loops run for as long as the app does. Here they run for a given number of cycles on the
test's thread: the function pacing them ends the loop once the cycles are done.
"""
import json
import os
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

# Internal imports.
import config
import data_layer
import models
import utils.mothership_interface
import utils.resilient_session
import utils.security
import utils.updater
from metrics import metrics_registry
from test.helpers import GlobalStateTestCase, close_store

# Third party imports.
import requests

APP_ID: str = "11111111-1111-1111-1111-111111111111"
"""The id of this app."""

MOTHERSHIP: str = "http://mothership:8181"
"""A mothership which is not the hub."""

TASK: dict = {"id": "22222222-2222-2222-2222-222222222222", "command": "restart"}
"""A task as a mothership hands it out."""


class _Response:
    """
    A response of requests, as far as the code under test reads one.
    """

    def __init__(self, body=None, status_code: int = 200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("{0} Error".format(self.status_code))

    def json(self):
        return self._body


class _Session:
    """
    Stands in for the session of a reporting or requesting thread. Answers each request with the next of the given
    answers - a response body, or an exception to raise.
    """

    def __init__(self, gets: list = None, posts: list = None):
        self.headers = {}
        self._gets = list(gets or [])
        self._posts = list(posts or [])
        self.requests: list[tuple[str, str, dict]] = []
        """Each request as (method, url, json body)."""

    def _answer(self, answers: list):
        answer = answers.pop(0) if answers else None
        if isinstance(answer, Exception):
            raise answer
        return _Response(answer)

    def get(self, url: str, timeout=None, headers=None):
        self.requests.append(("GET", url, None))
        return self._answer(self._gets)

    def post(self, url: str, timeout=None, json=None):
        self.requests.append(("POST", url, json))
        return self._answer(self._posts)

    def urls(self, method: str) -> list[str]:
        return [url for request_method, url, _ in self.requests if request_method == method]

    def reports(self, url: str) -> list[dict]:
        return [body for method, request_url, body in self.requests if method == "POST" and request_url == url]


class _MothershipTestCase(GlobalStateTestCase):

    def setUp(self):
        super().setUp()
        os.environ["APP_ID"] = APP_ID
        os.environ["APP_DESCRIPTION"] = "press-3"
        os.environ["HUB_API_ACCESS_TOKEN"] = "the-apps-own-token"

    def _run_cycles(self, loop, cycles: int, session: _Session, *args):
        """
        Run one of the reporting or requesting loops for the given number of cycles, on this thread.

        :param loop: The loop.
        :param cycles: The number of cycles.
        :param session: Stands in for the session of the loop.
        :param args: The arguments of the loop.
        """
        done = []

        def sleep_remaining(cycle_start: float, interval: int):
            done.append(interval)
            if len(done) >= cycles:
                data_layer.running = False

        with mock.patch.object(utils.mothership_interface, "_sleep_remaining", side_effect=sleep_remaining), \
                mock.patch.object(utils.resilient_session, "create_resilient_session", return_value=session):
            loop(*args)
        data_layer.running = True


class TestAllowedCommands(GlobalStateTestCase):

    def test_the_allowed_commands_are_read_from_the_settings(self):
        os.environ["ALLOWED_COMMANDS"] = "restart, start,stop "
        self.assertEqual(utils.mothership_interface._allowed_commands(), ["restart", "start", "stop"])

    def test_no_command_is_allowed_unless_named(self):
        os.environ.pop("ALLOWED_COMMANDS", None)
        self.assertEqual(utils.mothership_interface._allowed_commands(), [])
        os.environ["ALLOWED_COMMANDS"] = ""
        self.assertEqual(utils.mothership_interface._allowed_commands(), [])


class TestProcessTasks(GlobalStateTestCase):
    """
    A task is a command somebody else sends. It is executed only if the operator allowed that command.
    """

    def setUp(self):
        super().setUp()
        os.environ["ALLOWED_COMMANDS"] = "restart,start,stop,update,load,save"
        data_layer.configuration = mock.Mock()
        data_layer.configuration.load_configuration_from_stream.return_value = {}
        data_layer.configuration.save_configuration_as_file.return_value = (True, "Saved.")
        patcher = mock.patch.multiple(utils.updater, restart_application=mock.DEFAULT, update_app=mock.DEFAULT)
        self.updater = patcher.start()
        self.addCleanup(patcher.stop)

    def _executed(self) -> list[str]:
        """The names of everything a task executed."""
        calls = [name for name, function in self.updater.items() if function.called]
        return calls + [call[0] for call in data_layer.configuration.method_calls]

    def test_nothing_is_executed_unless_the_command_is_allowed(self):
        """
        An unset ALLOWED_COMMANDS used to allow every command, through a conditional expression that read as a
        filtered list.
        """
        for allowed in (None, "", "start"):
            with self.subTest(allowed=allowed):
                if allowed is None:
                    os.environ.pop("ALLOWED_COMMANDS", None)
                else:
                    os.environ["ALLOWED_COMMANDS"] = allowed
                with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
                    for command in ("restart", "stop", "update", "load", "save"):
                        utils.mothership_interface.process_tasks({"command": command})
                self.assertEqual(self._executed(), [])
                self.assertIn("Received not permitted task with command: 'restart'.", logs.output[0])

    def test_restart(self):
        utils.mothership_interface.process_tasks({"command": "restart"})
        self.updater["restart_application"].assert_called_once_with()

    def test_start_restarts_the_configuration(self):
        utils.mothership_interface.process_tasks({"command": "start"})
        data_layer.configuration.restart.assert_called_once_with()

    def test_stop_stops_the_configuration(self):
        utils.mothership_interface.process_tasks({"command": "stop"})
        data_layer.configuration.stop.assert_called_once_with()

    def test_load_starts_the_configuration_of_the_task(self):
        configuration = [{"id": "source", "module_name": "inputs.test.source_1.variable", "version": 1}]
        utils.mothership_interface.process_tasks({"command": "load", "configuration": configuration})
        data_layer.configuration.load_configuration_from_stream.assert_called_once_with(
            content=json.dumps(configuration))

    def test_a_configuration_which_can_not_be_loaded_is_reported(self):
        data_layer.configuration.load_configuration_from_stream.return_value = {"source": ["Invalid."]}
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
            utils.mothership_interface.process_tasks({"command": "load", "configuration": []})
        self.assertIn("source: ['Invalid.']", logs.output[0])

    def test_save_writes_the_configuration_of_the_task(self):
        utils.mothership_interface.process_tasks({"command": "save", "configuration": []})
        data_layer.configuration.save_configuration_as_file.assert_called_once_with(content="[]")

    def test_a_configuration_which_can_not_be_saved_is_reported(self):
        data_layer.configuration.save_configuration_as_file.return_value = (False, "Not valid.")
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
            utils.mothership_interface.process_tasks({"command": "save", "configuration": []})
        self.assertIn("Not valid.", logs.output[0])

    def test_update(self):
        utils.mothership_interface.process_tasks({"command": "update"})
        self.updater["update_app"].assert_called_once_with()

    def test_update_stores_the_git_access_token_of_the_task_first(self):
        root = self.enter_app_directory()
        utils.mothership_interface.process_tasks({"command": "update", "git_access_token": "-----BEGIN KEY-----"})
        with open(os.path.join(root, "git_access_token.txt"), encoding="utf-8") as file:
            self.assertEqual(file.read(), "-----BEGIN KEY-----")
        self.updater["update_app"].assert_called_once_with()

    def test_an_unknown_command_is_reported(self):
        os.environ["ALLOWED_COMMANDS"] = "reboot"
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
            utils.mothership_interface.process_tasks({"command": "reboot"})
        self.assertIn("Received task with unknown command: 'reboot'.", logs.output[0])
        self.assertEqual(self._executed(), [])


class TestRequestingTasksFromTheHub(_MothershipTestCase):
    """
    A task from the hub is executed only if its signature is the hub's, and only once.
    """

    def setUp(self):
        super().setUp()
        self.patch_config(VERIFY_TASK_SIGNATURE=True)
        patcher = mock.patch.object(utils.mothership_interface, "process_tasks")
        self.process_tasks = patcher.start()
        self.addCleanup(patcher.stop)

    def _request(self, session: _Session, cycles: int = 1, verified: bool = True, replay: bool = False):
        with mock.patch.object(utils.security, "verify_task_signature", return_value=verified) as verify, \
                mock.patch.object(utils.security, "is_replay", return_value=replay):
            self._run_cycles(utils.mothership_interface._request_hub_tasks, cycles, session)
        return verify

    def test_a_verified_task_is_executed(self):
        session = _Session(gets=[[TASK]])
        verify = self._request(session)

        verify.assert_called_once_with(task=TASK)
        self.process_tasks.assert_called_once_with(TASK)
        self.assertEqual(session.urls("POST"), [config.HUB_TEST_TOKEN_ADDRESS])
        self.assertEqual(session.urls("GET"), [f"{config.HUB_TASK_ADDRESS}/{APP_ID}"])
        self.assertEqual(session.headers["Authorization"], "Bearer the-apps-own-token")

    def test_a_task_whose_signature_is_not_the_hubs_is_not_executed(self):
        with self.assertLogs(utils.mothership_interface.logger, level="CRITICAL") as logs:
            self._request(_Session(gets=[[TASK]]), verified=False)
        self.process_tasks.assert_not_called()
        self.assertIn("Task signature verification failed", logs.output[0])

    def test_a_task_delivered_a_second_time_is_not_executed(self):
        with self.assertLogs(utils.mothership_interface.logger, level="CRITICAL") as logs:
            self._request(_Session(gets=[[TASK]]), replay=True)
        self.process_tasks.assert_not_called()
        self.assertIn("a second time", logs.output[0])

    def test_without_signature_verification_every_task_is_executed(self):
        self.patch_config(VERIFY_TASK_SIGNATURE=False)
        verify = self._request(_Session(gets=[[TASK]]), verified=False)
        verify.assert_not_called()
        self.process_tasks.assert_called_once_with(TASK)

    def test_after_a_failed_request_the_app_logs_in_again(self):
        session = _Session(gets=[requests.ConnectionError("The hub is not reachable."), [TASK]])
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
            self._request(session, cycles=2)
        self.assertIn("The hub is not reachable.", logs.output[0])
        self.assertEqual(len(session.urls("POST")), 2)
        self.process_tasks.assert_called_once_with(TASK)

    def test_no_task_is_requested_with_an_invalid_token(self):
        session = _Session(posts=[requests.HTTPError("401 Error")])
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
            self._request(session)
        self.assertIn("Invalid api access token", logs.output[0])
        self.assertEqual(session.urls("GET"), [])


class TestReportingToTheHub(_MothershipTestCase):
    """
    The app reports its state to the hub on every cycle - but what did not change since the last report that went
    through is left out.
    """

    def test_the_report_is_sent_with_the_id_of_the_app(self):
        session = _Session()
        self._run_cycles(utils.mothership_interface._report_hub, 1, session)

        (report,) = session.reports(config.HUB_APP_ADDRESS)
        self.assertEqual((report["app_id"], report["status"], report["description"]), (APP_ID, "inactive", "press-3"))
        for key in ("configuration", "installed_packages", "latest_logs", "module_count", "hostname", "site"):
            self.assertIn(key, report)

    def test_what_did_not_change_is_not_sent_again(self):
        session = _Session()
        self._run_cycles(utils.mothership_interface._report_hub, 2, session)

        first, second = session.reports(config.HUB_APP_ADDRESS)
        self.assertIn("configuration", first)
        self.assertNotIn("configuration", second)
        self.assertNotIn("installed_packages", second)

    def test_a_report_which_failed_is_sent_again_completely(self):
        # Logging in, the report that fails, logging in again, and the one that goes through.
        session = _Session(posts=[None, requests.ConnectionError("The hub is not reachable."), None, None])
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR"):
            self._run_cycles(utils.mothership_interface._report_hub, 2, session)

        reports = session.reports(config.HUB_APP_ADDRESS)
        self.assertEqual(len(reports), 2)
        self.assertIn("configuration", reports[1])
        self.assertEqual(session.urls("POST").count(config.HUB_TEST_TOKEN_ADDRESS), 2)


class TestPeerMotherships(_MothershipTestCase):
    """
    A mothership other than the hub is reported to, and asked for tasks, the same way.
    """

    def test_the_report_is_sent_to_the_mothership(self):
        session = _Session()
        self._run_cycles(utils.mothership_interface._report, 1, session, MOTHERSHIP)
        (report,) = session.reports(f"{MOTHERSHIP}/api/v1/app")
        self.assertEqual(report["app_id"], APP_ID)

    def test_tasks_are_requested_and_executed(self):
        session = _Session(gets=[[TASK]])
        with mock.patch.object(utils.mothership_interface, "process_tasks") as process_tasks:
            self._run_cycles(utils.mothership_interface._request_tasks, 1, session, MOTHERSHIP)
        self.assertEqual(session.urls("GET"), [f"{MOTHERSHIP}/api/v1/task/app_id/{APP_ID}"])
        process_tasks.assert_called_once_with(TASK)

    def test_an_unreachable_mothership_is_reported_once_per_interval(self):
        session = _Session(gets=[requests.ConnectionError("Unreachable.")] * 3)
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
            self._run_cycles(utils.mothership_interface._request_tasks, 3, session, MOTHERSHIP)
        self.assertEqual(len(session.urls("GET")), 3)
        self.assertEqual(len(logs.output), 1)


class TestReportData(GlobalStateTestCase):
    """
    What a report holds.
    """

    def setUp(self):
        super().setUp()
        for level in ("AREA", "WORK_CENTER", "WORK_UNIT", "EQUIPMENT_MODULE"):
            os.environ.pop(level, None)
        os.environ["APP_DESCRIPTION"] = "press-3"
        os.environ["SITE"] = "Stuttgart"
        os.environ["ALLOWED_COMMANDS"] = "restart"
        data_layer.version = "v1.75.0-0-gabcdef0"
        data_layer.configuration = mock.Mock(configuration_dict=[{"id": "source"}])

    @staticmethod
    def _log(message: str, minutes: int) -> models.Data:
        return models.Data(measurement="Logs", fields={"level": "INFO", "message": message, "module": "test",
                                                       "name": "test"},
                           time=datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes))

    def test_the_state_of_the_app(self):
        report, _, _, _ = utils.mothership_interface._get_report_data()

        self.assertEqual({key: report[key] for key in ("status", "version", "description", "allowed_commands",
                                                       "site", "area", "configuration")},
                         {"status": "inactive", "version": "v1.75.0-0-gabcdef0", "description": "press-3",
                          "allowed_commands": ["restart"], "site": "Stuttgart", "area": "",
                          "configuration": [{"id": "source"}]})
        for key in ("processed_per_min_avg", "module_count", "hostname", "os", "python_version", "disk_free_gb"):
            self.assertIn(key, report)

    def test_an_app_with_modules_is_running(self):
        data_layer.module_data["source"] = mock.Mock()
        self.assertEqual(utils.mothership_interface._get_report_data()[0]["status"], "running")

    def test_the_configuration_and_packages_are_only_sent_when_they_changed(self):
        _, _, configuration, packages = utils.mothership_interface._get_report_data()

        report, _, _, _ = utils.mothership_interface._get_report_data(last_configuration=configuration,
                                                                      last_installed_packages=packages)
        self.assertNotIn("configuration", report)
        self.assertNotIn("installed_packages", report)

        data_layer.configuration.configuration_dict = [{"id": "changed"}]
        report, _, _, _ = utils.mothership_interface._get_report_data(last_configuration=configuration,
                                                                      last_installed_packages=packages)
        self.assertEqual(report["configuration"], [{"id": "changed"}])

    def test_only_the_logs_not_sent_yet_are_included(self):
        for minutes, message in enumerate(("first", "second", "third")):
            data_layer.latest_logs.append(self._log(message, minutes))

        report, newest, _, _ = utils.mothership_interface._get_report_data()
        self.assertEqual([log["message"] for log in report["latest_logs"]], ["first", "second", "third"])
        self.assertEqual(report["latest_logs"][0]["time"], "2026-10-01T00:00:00+00:00")

        data_layer.latest_logs.append(self._log("fourth", 3))
        report, newer, _, _ = utils.mothership_interface._get_report_data(last_log_time=newest)
        self.assertEqual([log["message"] for log in report["latest_logs"]], ["fourth"])
        self.assertGreater(newer, newest)

        report, unchanged, _, _ = utils.mothership_interface._get_report_data(last_log_time=newer)
        self.assertEqual((report["latest_logs"], unchanged), ([], newer))

    def test_the_overall_performance_is_included(self):
        metrics_registry.register(module_id="source", module_name="inputs.test.source_1.variable")
        report, _, _, _ = utils.mothership_interface._get_report_data()
        self.assertEqual(report["module_count"], 1)


class TestInstalledPackages(unittest.TestCase):

    @staticmethod
    def _distribution(name, version="1.0"):
        return types.SimpleNamespace(metadata={"Name": name}, version=version)

    def test_the_packages_of_this_environment_are_listed(self):
        names = [package.name.lower() for package in utils.mothership_interface._get_installed_packages()]
        self.assertIn("requests", names)
        self.assertEqual(names, sorted(names))

    def test_a_package_is_listed_once_and_unreadable_ones_are_skipped(self):
        class Unreadable:
            @property
            def metadata(self):
                raise OSError("Broken dist-info.")

        distributions = [self._distribution("zeta"), self._distribution("Alpha", "2.0"), Unreadable(),
                         self._distribution("alpha", "1.0"), self._distribution(None)]
        with mock.patch.object(utils.mothership_interface.importlib.metadata, "distributions",
                               return_value=distributions):
            packages = utils.mothership_interface._get_installed_packages()

        self.assertEqual([(package.name, package.version) for package in packages], [("Alpha", "2.0"),
                                                                                     ("zeta", "1.0")])


class TestSystemStatistics(unittest.TestCase):

    def test_the_machine_is_described(self):
        stats = utils.mothership_interface._get_system_stats()
        self.assertEqual(set(stats), {"hostname", "os", "cpu_count", "cpu_architecture", "python_version",
                                      "disk_total_gb", "disk_used_gb", "disk_free_gb"})
        self.assertGreater(stats["disk_total_gb"], 0)


class TestThrottledErrors(GlobalStateTestCase):
    """
    An unreachable mothership is retried every few seconds, but logged only once per interval.
    """

    def test_an_error_is_logged_once_per_interval_and_key(self):
        log_times = {}
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR") as logs:
            for key in ("first", "first", "second", "first"):
                utils.mothership_interface._log_error_throttled(log_times, key, f"Error of {key}.")
        self.assertEqual(logs.output, [f"ERROR:{utils.mothership_interface.logger.name}:Error of first.",
                                       f"ERROR:{utils.mothership_interface.logger.name}:Error of second."])

    def test_an_error_is_logged_again_after_the_interval(self):
        log_times = {"first": datetime.now() - timedelta(
            seconds=config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL + 1)}
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR"):
            utils.mothership_interface._log_error_throttled(log_times, "first", "Error of first.")


class TestPacing(unittest.TestCase):
    """
    A cycle starts every interval, however long the previous one took.
    """

    def _sleep_remaining(self, elapsed: float, interval: int) -> mock.Mock:
        clock = types.SimpleNamespace(monotonic=lambda: 100.0 + elapsed, sleep=mock.Mock())
        with mock.patch.object(utils.mothership_interface, "time", clock):
            utils.mothership_interface._sleep_remaining(cycle_start=100.0, interval=interval)
        return clock.sleep

    def test_the_rest_of_the_interval_is_slept(self):
        self.assertEqual(self._sleep_remaining(elapsed=2, interval=5).call_args, mock.call(3))

    def test_a_cycle_which_took_longer_than_the_interval_is_followed_at_once(self):
        self._sleep_remaining(elapsed=6, interval=5).assert_not_called()


class TestStart(GlobalStateTestCase):
    """
    utils.mothership_interface.start: one reporting and one requesting thread for every mothership.
    """

    def setUp(self):
        super().setUp()
        for name, replacement in (("DatabaseWorker", mock.DEFAULT), ("Thread", mock.DEFAULT),
                                  ("time", types.SimpleNamespace(sleep=mock.Mock()))):
            patcher = mock.patch.object(utils.mothership_interface, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ["MOTHERSHIPS"] = "[]"
        os.environ["REPORT_TO_HUB"] = "0"
        os.environ.pop("HUB_API_ACCESS_TOKEN", None)

    @staticmethod
    def _threads() -> list[str]:
        return [call.kwargs["name"] for call in utils.mothership_interface.Thread.call_args_list]

    def test_the_hub_is_reported_to_with_a_token(self):
        os.environ["REPORT_TO_HUB"] = "1"
        os.environ["HUB_API_ACCESS_TOKEN"] = "the-apps-own-token"
        utils.mothership_interface.start()
        self.assertEqual(self._threads(), ["Mothership_Hub_Report_Worker", "Mothership_Hub_Request_Worker"])

    def test_the_hub_is_not_reported_to_without_a_token(self):
        os.environ["REPORT_TO_HUB"] = "1"
        with self.assertLogs(utils.mothership_interface.logger, level="ERROR"):
            utils.mothership_interface.start()
        self.assertEqual(self._threads(), [])

    def test_every_mothership_is_reported_to(self):
        os.environ["MOTHERSHIPS"] = json.dumps(["http://a:8181", "http://b:8181"])
        utils.mothership_interface.start()
        self.assertEqual(self._threads(), ["Mothership_Report_Worker_http://a:8181",
                                           "Mothership_Request_Worker_http://a:8181",
                                           "Mothership_Report_Worker_http://b:8181",
                                           "Mothership_Request_Worker_http://b:8181"])
        utils.mothership_interface.DatabaseWorker.assert_called_once_with()


class TestDatabaseWorker(GlobalStateTestCase):
    """
    The apps reporting to this one are kept in a database, so they are still listed after a restart.
    """

    def setUp(self):
        super().setUp()
        self.enter_app_directory()

    def _worker(self) -> utils.mothership_interface.DatabaseWorker:
        with mock.patch.object(utils.mothership_interface, "Thread"):
            worker = utils.mothership_interface.DatabaseWorker()
        self.addCleanup(close_store, worker.db)
        return worker

    @staticmethod
    def _check(worker: utils.mothership_interface.DatabaseWorker):
        """Run one cycle of the worker on this thread."""
        stop = types.SimpleNamespace(sleep=lambda seconds: setattr(data_layer, "running", False))
        with mock.patch.object(utils.mothership_interface, "time", stop):
            worker._checker()
        data_layer.running = True

    @staticmethod
    def _app(app_id: str = "app", **kwargs) -> models.MothershipData:
        return models.MothershipData(**{"app_id": app_id, "status": "running", "description": "press-3",
                                        "version": "v1.75.0", **kwargs})

    def test_a_reporting_app_is_stored(self):
        worker = self._worker()
        data_layer.mothership_data["app"] = self._app(hostname="plc-host", cpu_count=4)

        self._check(worker)

        entry = worker.db.get("id", "app")
        self.assertEqual((entry["description"], entry["hostname"], entry["cpu_count"]), ("press-3", "plc-host", 4))

    def test_the_stored_apps_are_known_after_a_restart_but_their_state_is_not(self):
        worker = self._worker()
        data_layer.mothership_data["app"] = self._app(hostname="plc-host")
        self._check(worker)
        close_store(worker.db)
        data_layer.mothership_data = {}

        self._worker()

        app = data_layer.mothership_data["app"]
        self.assertEqual((app.status, app.description, app.hostname), ("unknown", "press-3", "plc-host"))

    def test_a_changed_app_is_updated(self):
        worker = self._worker()
        data_layer.mothership_data["app"] = self._app()
        self._check(worker)

        data_layer.mothership_data["app"].description = "press-4"
        self._check(worker)

        self.assertEqual(worker.db.get("id", "app")["description"], "press-4")

    def test_a_deleted_app_is_removed(self):
        worker = self._worker()
        data_layer.mothership_data["app"] = self._app()
        self._check(worker)

        del data_layer.mothership_data["app"]
        self._check(worker)

        self.assertEqual(worker.db.all(), [])

    def test_an_app_which_stopped_reporting_is_unknown(self):
        worker = self._worker()
        data_layer.mothership_data["app"] = self._app(
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=config.REPORTER_TIMEOUT + 1))

        self._check(worker)

        self.assertEqual(data_layer.mothership_data["app"].status, "unknown")


if __name__ == '__main__':
    unittest.main()
