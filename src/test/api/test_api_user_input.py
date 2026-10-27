"""
Who submitted user input, as told to a module which asks for it - e.g. an approval step recording who approved.
"""
import os
import types
import unittest
from unittest import mock

# Internal imports.
import data_layer
from test.helpers import GlobalStateTestCase

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "routers", "deps.py")):
        raise ImportError("The interface submodule is not checked out.")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import interface.api_v1.routers.deps as deps
    import interface.api_v1.routers.v1.user_input as user_input
    from interface.api_v1.routers.v1 import api_router

    api_available = True
except ImportError:
    # `interface` is a submodule, which CI does not check out, and FastAPI is among the submodule's requirements
    # rather than this repository's.
    api_available = False


class AsksForTheUser:
    """A module whose store_data takes the user."""

    def __init__(self):
        self.received = []

    def store_data(self, data, user=None):
        self.received.append((data, user))


class DoesNotAsk:
    """A module whose store_data takes the data only, like every module before."""

    def __init__(self):
        self.received = []

    def store_data(self, data):
        self.received.append(data)


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestUserInputUser(GlobalStateTestCase):
    """
    A module asking for the user learns who submitted the data, and one which does not ask is called as before.
    """

    def setUp(self):
        super().setUp()
        os.environ.update({"API_AUTHENTICATION": "1", "APP_ID": "11111111-1111-1111-1111-111111111111"})
        self.app = FastAPI()
        self.app.include_router(api_router, prefix="/api/v1")
        self.client = TestClient(self.app, base_url="https://testserver")
        self.asks = AsksForTheUser()
        self.does_not_ask = DoesNotAsk()
        data_layer.module_data = {"asks": types.SimpleNamespace(instance=self.asks),
                                  "does_not_ask": types.SimpleNamespace(instance=self.does_not_ask)}

    def _as(self, caller):
        self.app.dependency_overrides[deps.get_identity] = lambda: caller

    def _send(self, module_id: str):
        response = self.client.post("/api/v1/user_input", json={"module_id": module_id, "measurement": "m",
                                                                 "fields": {"decision": "approved"}, "tags": {}})
        self.assertEqual(response.status_code, 204)

    def test_the_local_administrator(self):
        self._as(deps._identity(username="admin", held=(), unrestricted=True, authentication_required=True))
        self._send("asks")
        data, user = self.asks.received[0]
        self.assertEqual(data.fields, {"decision": "approved"})
        self.assertEqual(user, {"username": "admin", "authenticated": True})

    def test_a_hub_account_is_asked_for_its_name_only_where_a_module_needs_it(self):
        self._as(deps._identity(username="", held=("app:read",), unrestricted=False, authentication_required=True,
                                owner_id="owner", hub_token="hub-token"))
        with mock.patch.object(user_input, "hub_username", return_value="max@bau.de") as hub_username:
            self._send("does_not_ask")
            hub_username.assert_not_called()
            self._send("asks")
        hub_username.assert_called_once_with("hub-token")
        self.assertEqual(self.asks.received[0][1], {"username": "max@bau.de", "authenticated": True})
        self.assertEqual(len(self.does_not_ask.received), 1)

    def test_without_authentication_the_user_is_unknown(self):
        self._as(deps._identity(username="", held=(), unrestricted=True, authentication_required=False))
        self._send("asks")
        self.assertEqual(self.asks.received[0][1], {"username": "", "authenticated": False})


if __name__ == "__main__":
    unittest.main()
