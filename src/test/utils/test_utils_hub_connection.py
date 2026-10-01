"""
Downloading, updating and publishing modules through the hub (utils.hub_connection). Nothing here talks to the hub:
it is stood in for by a session answering from a table.
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

# Internal imports.
import config
import data_layer
import utils.hub_connection
import utils.plugin_interface
import utils.resilient_session
from test.helpers import GlobalStateTestCase

# Third party imports.
import requests

CODE: str = '"""A module of the tests."""\n__version__: int = 2\n'
"""The code of a module, as the hub stores it."""


def _module(module_name: str, key: str = "latest", **version) -> dict:
    """
    A module as the hub answers it: under 'version' when one was asked for, and under 'latest' otherwise.
    """
    return {"id": "module-id", "module_name": module_name, key: version}


class _Response:
    """
    A response of requests, as far as the code under test reads one.
    """

    def __init__(self, body=None, status_code: int = 200):
        self._body = body
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError("{0} Error".format(self.status_code))

    def json(self):
        return self._body


class _Hub:
    """
    Stands in for an authenticated session with the hub.

    :param modules: What the hub answers for a module name, as get_by_module_name does. Unknown names are answered 404.
    :param lists: What the hub answers for a list of modules, by endpoint.
    """

    def __init__(self, modules: dict[str, dict] = None, lists: dict[str, list] = None):
        self.headers = {}
        self.modules = modules or {}
        self.lists = lists or {}
        self.requests: list[tuple] = []
        """Each request as (method, url, params or the sent json)."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str, params: dict = None, allow_redirects=None, timeout=None):
        self.requests.append(("GET", url, params))
        if url.endswith("/get_by_module_name"):
            body = self.modules.get(params["module_name"])
            return _Response(body, 200 if body is not None else 404)
        if url == config.HUB_TEST_TOKEN_ADDRESS:
            return _Response({"username": "acme"})
        return _Response(self.lists.get(url.rsplit("/", 1)[-1], []))

    def _store(self, method: str, url: str, data: str):
        sent = json.loads(data)
        self.requests.append((method, url, sent))
        return _Response({"id": "module-id", "version": {"code": sent["code"]}})

    def put(self, url: str, data: str = None, allow_redirects=None, timeout=None):
        return self._store("PUT", url, data)

    def post(self, url: str, data: str = None, allow_redirects=None, timeout=None):
        return self._store("POST", url, data)

    def sent(self, method: str) -> list:
        return [(url, body) for request_method, url, body in self.requests if request_method == method]


class _HubTestCase(GlobalStateTestCase):

    def setUp(self):
        super().setUp()
        os.environ["HUB_API_ACCESS_TOKEN"] = "the-apps-own-token"
        patcher = mock.patch.object(utils.plugin_interface, "write_module_to_file")
        self.written = patcher.start()
        self.addCleanup(patcher.stop)

    def _session(self, hub) -> mock.Mock:
        """Let create_authenticated_session answer with the given session, or None."""
        patcher = mock.patch.object(utils.hub_connection, "create_authenticated_session", return_value=hub)
        self.addCleanup(patcher.stop)
        return patcher.start()


class TestCreateAuthenticatedSession(_HubTestCase):

    def _create(self, hub: _Hub):
        with mock.patch.object(utils.resilient_session, "create_resilient_session", return_value=hub):
            return utils.hub_connection.create_authenticated_session()

    def test_the_token_of_the_app_is_used_and_tested(self):
        hub = _Hub()
        self.assertIs(self._create(hub), hub)
        self.assertEqual(hub.headers, {"Authorization": "Bearer the-apps-own-token"})
        self.assertEqual(hub.requests, [("GET", config.HUB_TEST_TOKEN_ADDRESS, None)])

    def test_an_invalid_token_gives_no_session(self):
        hub = _Hub()
        hub.get = mock.Mock(return_value=_Response(status_code=401))
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            self.assertIsNone(self._create(hub))


class TestIsNewerThanRegistered(GlobalStateTestCase):
    """
    A module is only written when the hub has a newer version than the one installed here.
    """

    def setUp(self):
        super().setUp()
        data_layer.registered_modules["inputs.test.client_1"] = SimpleNamespace(version=2)
        data_layer.registered_modules["inputs.test.client_1.variable"] = SimpleNamespace(version=2)

    @staticmethod
    def _newer(module_name: str, **answer) -> bool:
        return utils.hub_connection._is_newer_than_registered({"module_name": module_name, **answer})

    def test_a_module_which_is_not_installed_is_newer(self):
        self.assertTrue(self._newer("outputs.test.collector_1", latest={"version": 1}))

    def test_the_versions_are_compared(self):
        self.assertTrue(self._newer("inputs.test.client_1", latest={"version": 3}))
        self.assertFalse(self._newer("inputs.test.client_1", latest={"version": 2}))
        self.assertFalse(self._newer("inputs.test.client_1", version={"version": 1}))

    def test_a_module_without_a_version_is_written(self):
        self.assertTrue(self._newer("inputs.test.client_1"))

    def test_the_module_names_of_variable_and_tag_modules_count_for_their_file(self):
        self.assertEqual(utils.hub_connection._base_name("inputs.test.client_1.variable"), "inputs.test.client_1")
        self.assertEqual(utils.hub_connection._base_name("inputs.test.client_1.tag"), "inputs.test.client_1")
        self.assertEqual(utils.hub_connection._base_name("outputs.test.collector_1"), "outputs.test.collector_1")


class TestDownloadModule(_HubTestCase):

    def test_the_code_of_the_requested_version_is_written(self):
        hub = _Hub(modules={"outputs.test.collector_1": _module("outputs.test.collector_1", "version", version=2, code=CODE)})

        self.assertTrue(utils.hub_connection.download_module("outputs.test.collector_1", version=2, session=hub))

        self.assertEqual(hub.requests, [("GET", f"{config.HUB_MODULES_ADDRESS}/get_by_module_name",
                                         {"module_name": "outputs.test.collector_1", "version": 2})])
        self.written.assert_called_once_with(module_name="outputs.test.collector_1", code=CODE)

    def test_the_latest_version_is_written_if_it_is_newer(self):
        data_layer.registered_modules["outputs.test.collector_1"] = SimpleNamespace(version=1)
        hub = _Hub(modules={"outputs.test.collector_1": _module("outputs.test.collector_1", version=2, code=CODE)})

        self.assertTrue(utils.hub_connection.download_module("outputs.test.collector_1", session=hub))

        self.written.assert_called_once_with(module_name="outputs.test.collector_1", code=CODE)

    def test_a_module_which_is_up_to_date_is_not_written_again(self):
        data_layer.registered_modules["outputs.test.collector_1"] = SimpleNamespace(version=2)
        hub = _Hub(modules={"outputs.test.collector_1": _module("outputs.test.collector_1", version=2, code=CODE)})

        self.assertTrue(utils.hub_connection.download_module("outputs.test.collector_1", session=hub))

        self.written.assert_not_called()

    def test_a_version_flagged_as_malicious_is_refused(self):
        hub = _Hub(modules={"outputs.test.collector_1": _module("outputs.test.collector_1", version=2, code=CODE,
                                                                 malicious=True)})

        with self.assertLogs(utils.hub_connection.logger, level="CRITICAL") as logs:
            self.assertFalse(utils.hub_connection.download_module("outputs.test.collector_1", session=hub))

        self.written.assert_not_called()
        self.assertIn("flagged this version as malicious", logs.output[0])

    def test_an_answer_without_code_is_refused(self):
        hub = _Hub(modules={"outputs.test.collector_1": _module("outputs.test.collector_1", version=2)})
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            self.assertFalse(utils.hub_connection.download_module("outputs.test.collector_1", session=hub))
        self.written.assert_not_called()

    def test_a_module_the_hub_does_not_know_is_reported(self):
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            self.assertFalse(utils.hub_connection.download_module("outputs.test.unknown_1", session=_Hub()))

    def test_the_name_is_cleaned_before_the_hub_is_asked(self):
        """
        A name copied from somewhere can carry invisible characters, and the name of a variable or tag module is
        the name of its file plus a suffix.
        """
        hub = _Hub(modules={"inputs.test.client_1": _module("inputs.test.client_1", version=1, code=CODE)})

        self.assertTrue(utils.hub_connection.download_module("\u200binputs.test.client_1.variable\ufeff \n",
                                                             session=hub))

        self.assertEqual(hub.requests[0][2]["module_name"], "inputs.test.client_1")
        self.written.assert_called_once_with(module_name="inputs.test.client_1", code=CODE)

    def test_a_session_is_created_if_none_is_given(self):
        hub = _Hub(modules={"outputs.test.collector_1": _module("outputs.test.collector_1", version=1, code=CODE)})
        self._session(hub)
        self.assertTrue(utils.hub_connection.download_module("outputs.test.collector_1"))

    def test_without_a_session_nothing_is_downloaded(self):
        self._session(None)
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            self.assertFalse(utils.hub_connection.download_module("outputs.test.collector_1"))


class TestDownloadModules(_HubTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(utils.hub_connection, "download_module", return_value=True)
        self.download_module = patcher.start()
        self.addCleanup(patcher.stop)

    def test_each_selection_is_downloaded_from_its_endpoints(self):
        for selection, endpoints in utils.hub_connection.MODULE_ENDPOINTS.items():
            with self.subTest(selection=selection):
                hub = _Hub(lists={endpoint: [{"module_name": f"outputs.test.{endpoint}_1"}]
                                  for endpoint in endpoints})
                self._session(hub)
                self.download_module.reset_mock()

                utils.hub_connection.download_modules(requested_module_types=selection)

                self.assertEqual(hub.requests, [("GET", f"{config.HUB_MODULES_ADDRESS}/{endpoint}",
                                                 {"only_allowed": "true"}) for endpoint in endpoints])
                self.assertEqual([call.kwargs for call in self.download_module.call_args_list],
                                 [{"module_name": f"outputs.test.{endpoint}_1", "version": 0, "session": hub}
                                  for endpoint in endpoints])

    def test_an_unknown_selection_is_refused(self):
        create = self._session(_Hub())
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            utils.hub_connection.download_modules(requested_module_types="everything")
        create.assert_not_called()

    def test_without_a_session_nothing_is_downloaded(self):
        self._session(None)
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            utils.hub_connection.download_modules()
        self.download_module.assert_not_called()

    def test_a_failing_hub_is_reported(self):
        hub = _Hub()
        hub.get = mock.Mock(side_effect=requests.ConnectionError("The hub is not reachable."))
        self._session(hub)
        with self.assertLogs(utils.hub_connection.logger, level="ERROR") as logs:
            utils.hub_connection.download_modules()
        self.assertIn("The hub is not reachable.", logs.output[-1])


class TestUpdateModules(_HubTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(utils.hub_connection, "download_module", return_value=True)
        self.download_module = patcher.start()
        self.addCleanup(patcher.stop)
        self.hub = _Hub()
        self._session(self.hub)

    def test_every_installed_module_is_updated_once(self):
        for name in ("outputs.test.collector_1", "inputs.test.client_1", "inputs.test.client_1.variable",
                     "inputs.test.client_1.tag"):
            data_layer.registered_modules[name] = SimpleNamespace(version=1)

        utils.hub_connection.update_modules()

        self.assertEqual([call.kwargs for call in self.download_module.call_args_list],
                         [{"module_name": "inputs.test.client_1", "session": self.hub},
                          {"module_name": "outputs.test.collector_1", "session": self.hub}])

    def test_the_given_modules_are_updated(self):
        utils.hub_connection.update_modules(module_names=["outputs.test.collector_1"])
        self.download_module.assert_called_once_with(module_name="outputs.test.collector_1", session=self.hub)

    def test_without_a_session_nothing_is_updated(self):
        self._session(None)
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            utils.hub_connection.update_modules(module_names=["outputs.test.collector_1"])
        self.download_module.assert_not_called()


class TestSendModules(_HubTestCase):
    """
    Publishing the modules of the custom module folder, or the ones named, to the hub.
    """

    def setUp(self):
        super().setUp()
        self.root = self.enter_app_directory()
        os.environ["CUSTOM_MODULE_FOLDER"] = "custom"
        self.code = self._write("modules/custom/outputs/test/collector_1.py", CODE.replace("2", "1"))
        self.hub = _Hub()
        self._session(self.hub)

    def _write(self, path: str, code: str) -> str:
        path = os.path.join(self.root, "src", path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(code)
        return code

    def test_a_module_the_hub_does_not_know_is_created(self):
        utils.hub_connection.send_modules(module_names=["outputs.test.collector_1"])

        self.assertEqual(self.hub.sent("POST"), [(config.HUB_MODULES_ADDRESS, {"code": self.code, "official": False,
                                                                               "module_name": "outputs.test.collector_1"})])
        self.written.assert_called_once_with(module_name="outputs.test.collector_1", code=self.code)

    def test_a_changed_module_is_updated(self):
        self.hub.modules["outputs.test.collector_1"] = _module("outputs.test.collector_1", "version",
                                                                code="# Older code.\n")

        utils.hub_connection.send_modules(module_names=["outputs.test.collector_1"])

        self.assertEqual(self.hub.sent("PUT"), [(f"{config.HUB_MODULES_ADDRESS}/module-id",
                                                 {"code": self.code, "official": False})])
        self.assertEqual(self.hub.sent("POST"), [])

    def test_a_module_whose_version_line_alone_differs_is_not_sent(self):
        """
        The hub writes the version itself, so the line is never the same as here.
        """
        self.hub.modules["outputs.test.collector_1"] = _module("outputs.test.collector_1", "version",
                                                                code=CODE.replace("2", "7"))

        utils.hub_connection.send_modules(module_names=["outputs.test.collector_1"])

        self.assertEqual(self.hub.sent("PUT") + self.hub.sent("POST"), [])
        self.written.assert_not_called()

    def test_all_modules_of_the_custom_module_folder_are_sent_by_default(self):
        self._write("modules/custom/processors/test/multiplier_1.py", "# A processor.\n")
        self._write("modules/custom/README.py", "# Not a module.\n")

        utils.hub_connection.send_modules(module_names=None)

        self.assertEqual(sorted(body["module_name"] for _, body in self.hub.sent("POST")),
                         ["outputs.test.collector_1", "processors.test.multiplier_1"])

    def test_a_module_which_can_not_be_found_is_reported(self):
        with self.assertLogs(utils.hub_connection.logger, level="ERROR") as logs:
            utils.hub_connection.send_modules(module_names=["outputs.test.missing_1"])
        self.assertIn("Could not find module: outputs.test.missing_1", logs.output[0])

    def test_without_a_custom_module_folder_the_modules_have_to_be_named(self):
        create = self._session(self.hub)
        os.environ.pop("CUSTOM_MODULE_FOLDER")
        with self.assertLogs(utils.hub_connection.logger, level="ERROR"):
            utils.hub_connection.send_modules(module_names=None)
        create.assert_not_called()


if __name__ == '__main__':
    unittest.main()
