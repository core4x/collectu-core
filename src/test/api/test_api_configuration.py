"""
The routes starting and checking configurations, and the one answering the logs - which are tools of the mcp server
as well, so what they answer is what an agent has to go on.
"""
import datetime
import logging
import os
import unittest
from unittest import mock

# Internal imports.
import data_layer
import models
import utils.hub_connection
import utils.logging
from test.helpers import AppTestCase, Client, Collector, module_config, wait_for

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "routers", "deps.py")):
        raise ImportError("The interface submodule is not checked out.")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from interface.api_v1.routers.v1 import api_router

    api_available = True
except ImportError:
    # `interface` is a submodule, which CI does not check out, and FastAPI is among the submodule's requirements
    # rather than this repository's.
    api_available = False

PIPELINE: list[dict] = [module_config("source", "inputs.test.source_1.variable", links=["collector"]),
                        module_config("collector", "outputs.test.collector_1")]
"""A source linked to an output."""


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class ApiTestCase(AppTestCase):
    """
    The api of an app without authentication, in front of a configuration of the fake modules.
    """

    def setUp(self):
        super().setUp()
        os.environ["API_AUTHENTICATION"] = "0"
        self.configuration = self.create_configuration()
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        self.client = TestClient(app, base_url="https://testserver")


class TestValidate(ApiTestCase):
    """
    POST /configuration/validate: a configuration is checked without side effects.
    """

    def test_a_valid_configuration_is_neither_started_nor_downloaded(self):
        response = self.client.post("/api/v1/configuration/validate", json={"configuration": PIPELINE})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"valid": True, "errors": [], "downloads": []})
        self.assertEqual(data_layer.module_data, {})

    def test_a_module_in_another_version_is_reported_instead_of_downloaded(self):
        os.environ["AUTO_DOWNLOAD"] = "1"
        with mock.patch.object(utils.hub_connection, "download_module") as download_module:
            response = self.client.post("/api/v1/configuration/validate",
                                        json={"configuration": [PIPELINE[0], dict(PIPELINE[1], version=2)]})

        download_module.assert_not_called()
        self.assertEqual(response.json(), {"valid": True, "errors": [], "downloads": [
            {"id": "collector", "module_name": "outputs.test.collector_1", "version": 2, "installed_version": 1}]})

    def test_the_errors_are_reported_by_module(self):
        response = self.client.post("/api/v1/configuration/validate",
                                    json={"configuration": [dict(PIPELINE[0], links=["missing"])]})

        result = response.json()
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"], [{"loc": ["body", "source"], "type": "value_error",
                                             "msg": "A linked module with the id 'missing' does not exist."}])


class TestStart(ApiTestCase):
    """
    POST /configuration/start and /configuration/start_from_file: what a started configuration resulted in.
    """

    def test_the_state_of_each_module_is_answered(self):
        response = self.client.post("/api/v1/configuration/start", json={"configuration": PIPELINE})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "modules": [{"id": "source", "module_name": "inputs.test.source_1.variable", "version": 1,
                         "state": "running", "start_error": None},
                        {"id": "collector", "module_name": "outputs.test.collector_1", "version": 1,
                         "state": "running", "start_error": None}],
            "downloaded": []})

    def test_a_module_downloaded_in_another_version_is_answered(self):
        """
        The download replaces the installed version - which is what the caller has to learn about.
        """
        os.environ["AUTO_DOWNLOAD"] = "1"

        class NewCollector(Collector):
            version = 2

        def download(module_name: str, version: int) -> bool:
            data_layer.registered_modules[module_name] = NewCollector
            return True

        with mock.patch.object(utils.hub_connection, "download_module", side_effect=download):
            response = self.client.post("/api/v1/configuration/start",
                                        json={"configuration": [PIPELINE[0], dict(PIPELINE[1], version=2)]})

        self.assertEqual(response.json()["downloaded"], [
            {"module_name": "outputs.test.collector_1", "version": 2, "replaced_version": 1}])

    def test_a_failing_start_is_answered_after_waiting(self):
        class Refused(Client):
            def start(self):
                raise ConnectionError("Connection refused.")

        data_layer.registered_modules["inputs.test.client_1"] = Refused
        with self.assertLogs("collectu.configuration", level="ERROR"):
            response = self.client.post("/api/v1/configuration/start", params={"wait_seconds": 0.2},
                                        json={"configuration": [module_config("client", "inputs.test.client_1")]})
            self.configuration.stop()

        self.assertEqual(response.json()["modules"], [
            {"id": "client", "module_name": "inputs.test.client_1", "version": 1,
             "state": "retrying", "start_error": "Connection refused."}])

    def test_an_invalid_configuration_is_refused_as_before(self):
        response = self.client.post("/api/v1/configuration/start",
                                    json={"configuration": [dict(PIPELINE[0], links=["missing"])]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "source"])

    def test_a_configuration_file_is_listed_and_started(self):
        self.write_configuration_file("line_3/press.yml",
                                      "- id: collector\n  module_name: outputs.test.collector_1\n  version: 1\n")

        self.assertEqual(self.client.get("/api/v1/configuration/files").json(), ["line_3/press.yml"])
        response = self.client.post("/api/v1/configuration/start_from_file", params={"filename": "line_3/press.yml"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([module["id"] for module in response.json()["modules"]], ["collector"])
        self.assertTrue(wait_for(lambda: "collector" in data_layer.module_data))


class TestLogs(ApiTestCase):
    """
    GET /log: the buffered logs, filtered.
    """

    def setUp(self):
        super().setUp()
        trigger = utils.logging.LoggingTrigger(levels=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        for name, level, message in (("collectu.inputs.test.client_1.client", "ERROR", "Connection refused."),
                                     ("collectu.configuration", "INFO", "Successfully set new configuration."),
                                     ("collectu.inputs.test.client_1.client", "WARNING", "Slow connection."),
                                     ("collectu.outputs.test.collector_1.collector", "INFO", "Stored 5 rows.")):
            trigger.emit(logging.LogRecord(name=name, level=getattr(logging, level), pathname=name + ".py", lineno=1,
                                           msg=message, args=None, exc_info=None))

    def _messages(self, **params) -> list[str]:
        response = self.client.get("/api/v1/log", params=params)
        self.assertEqual(response.status_code, 200)
        return [log["message"] for log in response.json()]

    def test_without_filters_every_log_is_answered(self):
        self.assertEqual(len(self._messages()), 4)

    def test_the_logs_are_filtered(self):
        self.assertEqual(self._messages(level="WARNING"), ["Connection refused.", "Slow connection."])
        self.assertEqual(self._messages(module_id="client"), ["Connection refused.", "Slow connection."])
        self.assertEqual(self._messages(search="ROWS"), ["Stored 5 rows."])
        self.assertEqual(self._messages(limit=2), ["Slow connection.", "Stored 5 rows."])
        self.assertEqual(self._messages(module_id="client", level="ERROR"), ["Connection refused."])

    def test_the_logs_after_a_time_are_answered(self):
        later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1)
        data_layer.latest_logs.append(models.Data(measurement="Logs", time=later + datetime.timedelta(seconds=1),
                                                  fields={"level": "INFO", "message": "Later.", "name": "client",
                                                          "module": "inputs.test.client_1"}))
        self.assertEqual(self._messages(since=later.isoformat()), ["Later."])
        self.assertEqual(self._messages(since=later.replace(tzinfo=None).isoformat()), ["Later."],
                         "A time without an offset is taken as UTC.")


if __name__ == '__main__':
    unittest.main()
