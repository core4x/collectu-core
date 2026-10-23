"""
The routes about modules which reach the hub: what the editor may offer to download, and whether it should.
"""
import os
import unittest
from unittest import mock

# Internal imports.
import utils.hub_connection
from test.helpers import GlobalStateTestCase

# Third party imports.
import requests

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

FOUND: dict = {"module_name": "outputs.test.collector_1", "module_type": "output", "version": 3, "public": True,
               "author": "Acme", "email": None, "description": "Collects.", "documentation": "# Collector",
               "deprecated": False, "third_party_requirements": [], "parameters": [{"key": "interval"}],
               "hub_id": "the-hubs-id", "official": True}
"""A module as utils.hub_connection.search_modules answers it."""


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class ModuleApiTestCase(GlobalStateTestCase):
    """
    The api of an app without authentication, which has a token of the hub.
    """

    def setUp(self):
        super().setUp()
        os.environ["API_AUTHENTICATION"] = "0"
        os.environ["HUB_API_ACCESS_TOKEN"] = "the-apps-own-token"
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        self.client = TestClient(app, base_url="https://testserver")

    def _search(self, **search_modules):
        patcher = mock.patch.object(utils.hub_connection, "search_modules", **search_modules)
        self.addCleanup(patcher.stop)
        return patcher.start()


class TestSearchHub(ModuleApiTestCase):
    """
    GET /module/hub: the hub's modules this app could download.
    """

    def test_the_modules_found_are_answered(self):
        search = self._search(return_value=[FOUND])

        response = self.client.get("/api/v1/module/hub", params={"search_keywords": "collector"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [FOUND])
        search.assert_called_once_with(search_keywords="collector")

    def test_without_a_token_of_the_hub_nothing_is_searched(self):
        os.environ["HUB_API_ACCESS_TOKEN"] = ""
        search = self._search(return_value=[FOUND])

        response = self.client.get("/api/v1/module/hub", params={"search_keywords": "collector"})

        self.assertEqual(response.status_code, 400)
        search.assert_not_called()

    def test_what_went_wrong_at_the_hub_is_answered_as_what_it_is(self):
        """
        The hub refusing this app's own token is never a 401: a client reads that as its own session having ended.
        """
        refused = requests.HTTPError(response=mock.Mock(status_code=401))
        failed = requests.HTTPError(response=mock.Mock(status_code=500))
        cases = [(refused, 502), (failed, 502), (ValueError("Not a page."), 502),
                 (requests.JSONDecodeError("Expecting value", "<html>", 0), 502),
                 (requests.ConnectionError(), 503)]
        for error, status_code in cases:
            with self.subTest(error=error):
                self._search(side_effect=error)
                with self.assertLogs(level="WARNING"):
                    response = self.client.get("/api/v1/module/hub", params={"search_keywords": "collector"})
                self.assertEqual(response.status_code, status_code)
                if error is refused:
                    self.assertIn("HUB_API_ACCESS_TOKEN", response.json()["detail"])


class TestCapabilities(ModuleApiTestCase):
    """
    GET /capabilities: whether the editor should offer the hub's modules at all.
    """

    def _auto_download(self) -> bool:
        return self.client.get("/api/v1/capabilities").json()["auto_download"]

    def test_the_hubs_modules_are_offered_where_starting_downloads_them(self):
        os.environ["AUTO_DOWNLOAD"] = "1"
        self.assertTrue(self._auto_download())

    def test_not_while_auto_download_is_switched_off(self):
        os.environ["AUTO_DOWNLOAD"] = "0"
        self.assertFalse(self._auto_download())

    def test_not_without_a_token_of_this_app_to_download_them_with(self):
        os.environ["AUTO_DOWNLOAD"] = "1"
        os.environ["HUB_API_ACCESS_TOKEN"] = ""
        self.assertFalse(self._auto_download())

    def test_a_value_which_is_not_a_number_does_not_fail_the_answer(self):
        os.environ["AUTO_DOWNLOAD"] = "yes"
        self.assertFalse(self._auto_download())


if __name__ == '__main__':
    unittest.main()
