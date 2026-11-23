"""
The local viewer: this app's second account (LOCAL_VIEWER_USERNAME / LOCAL_VIEWER_PASSWORD), for whoever watches the
machine where there is no hub to sign in with - see interface/api_v1/routers/deps.py.

It signs in with a password like the local administrator, may read what this app shows and use its input forms like a
viewer of the hub, and nothing else. It has no hub account, and never borrows this app's token to reach the hub.
"""
import os
import unittest
from unittest import mock

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "routers", "deps.py")):
        raise ImportError("The interface submodule is not checked out.")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import interface.api_v1.routers.deps as deps
    import interface.api_v1.routers.v1.hub_proxy as hub_proxy
    import interface.api_v1.routers.v1.login as login
    from interface.api_v1.routers.v1 import api_router
    from test.api.test_api_permissions import ENVIRONMENT, FakeResponse

    api_available = True
except ImportError:
    api_available = False

VIEWER_ENVIRONMENT: dict[str, str] = {"LOCAL_VIEWER_USERNAME": "viewer", "LOCAL_VIEWER_PASSWORD": "watch"}
"""The local viewer, next to the local administrator of ENVIRONMENT."""


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestLocalViewer(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {**ENVIRONMENT, **VIEWER_ENVIRONMENT})
        patcher.start()
        self.addCleanup(patcher.stop)
        deps.forget_identity()
        self.addCleanup(deps.forget_identity)
        # Nothing of the local accounts asks the hub.
        patcher = mock.patch.object(deps.session, "get", side_effect=AssertionError("The hub was asked."))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(hub_proxy.requests, "request", return_value=FakeResponse(body={}))
        self.forward = patcher.start()
        self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        self.client = TestClient(app, base_url="https://testserver")

    def _sign_in(self, username: str = "viewer", password: str = "watch"):
        return self.client.post("/api/v1/login/access-token", data={"username": username, "password": password})

    def _bearer(self, username: str = "viewer", password: str = "watch") -> dict[str, str]:
        response = self._sign_in(username, password)
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    def test_the_local_viewer_signs_in_and_may_read(self):
        response = self.client.get("/api/v1/login/test-token", headers=self._bearer())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["username"], "viewer")
        self.assertEqual(body["permissions"], ["app:read", "module:read", "configuration:read"])
        self.assertFalse(body["hub_access"], "A client offers it nothing of the hub.")
        self.assertIsNone(body["owner_id"])
        self.assertTrue(body["authentication_required"])

    def test_the_local_administrator_still_may_do_everything(self):
        body = self.client.get("/api/v1/login/test-token", headers=self._bearer("admin", "password")).json()
        self.assertEqual(body["username"], "admin")
        self.assertEqual(body["permissions"], [permission.value for permission in deps.P])
        self.assertTrue(body["hub_access"])

    def test_the_local_viewer_uses_the_input_forms(self):
        headers = self._bearer()
        self.assertEqual(self.client.get("/api/v1/user_input", headers=headers).status_code, 200)
        response = self.client.post("/api/v1/user_input", headers=headers,
                                    json={"module_id": "no-such-module", "measurement": "m", "fields": {}, "tags": {}})
        self.assertEqual(response.status_code, 404, "Past the permissions, and refused for want of the module.")

    def test_the_local_viewer_commands_and_changes_nothing(self):
        headers = self._bearer()
        refused = [("POST", "/api/v1/update/restart", "task:create"),
                   ("POST", "/api/v1/configuration/stop", "task:create"),
                   ("PUT", "/api/v1/dashboard/layout", "task:create"),
                   ("GET", "/api/v1/settings", "app:update"),
                   ("PUT", "/api/v1/settings", "app:update"),
                   ("DELETE", "/api/v1/configuration/some-id", "configuration:delete"),
                   ("POST", "/api/v1/module/update", "module:update")]
        with mock.patch("utils.updater.restart_application") as restart:
            for method, path, permission in refused:
                with self.subTest(method=method, path=path):
                    response = self.client.request(method, path, headers=headers, json={})
                    self.assertEqual(response.status_code, 403)
                    self.assertIn(permission, response.json()["detail"])
        restart.assert_not_called()

    def test_the_local_viewer_does_not_reach_the_hub_with_this_apps_token(self):
        """
        This app's token may do far more at the hub than read - and read its secrets.
        """
        headers = self._bearer()
        for method in ("GET", "POST", "PUT", "DELETE"):
            with self.subTest(method=method):
                response = self.client.request(method, "/api/v1/hub_proxy/module/my", headers=headers)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"], hub_proxy.NO_HUB_ACCESS)
        self.forward.assert_not_called()

        response = self.client.get("/api/v1/hub_proxy/module/my", headers=self._bearer("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.forward.call_args.kwargs["headers"]["Authorization"], "Bearer the-apps-own-token")

    def test_without_a_password_there_is_no_local_viewer(self):
        os.environ["LOCAL_VIEWER_PASSWORD"] = ""
        response = self._sign_in("viewer", "watch")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], login.NOT_THE_LOCAL_ADMINISTRATOR)

    def test_a_wrong_password_of_the_local_viewer_is_refused(self):
        self.assertEqual(self._sign_in("viewer", "password").status_code, 401)
        self.assertEqual(self._sign_in("admin", "watch").status_code, 401, "Each account by its own password.")

    def test_there_is_no_local_viewer_by_the_local_administrators_name(self):
        """
        One name for two accounts would leave it to chance which one signs in.
        """
        os.environ["LOCAL_VIEWER_USERNAME"] = "admin"
        self.assertEqual(self._sign_in("admin", "watch").status_code, 401)
        body = self.client.get("/api/v1/login/test-token", headers=self._bearer("admin", "password")).json()
        self.assertEqual(body["permissions"], [permission.value for permission in deps.P])

    def test_a_token_of_the_local_viewer_never_becomes_the_administrators(self):
        """
        A token names its account by its role as well as its name: renamed, the administrator does not take over the
        viewer's tokens.
        """
        headers = self._bearer()
        # A token this app does not recognize as its own goes to the hub, which did not sign it either.
        refused = FakeResponse(status_code=401, body={"detail": "Could not validate credentials."})
        with mock.patch.object(deps.session, "get", return_value=refused):
            with mock.patch.dict(os.environ, {"LOCAL_ADMIN_USERNAME": "viewer", "LOCAL_VIEWER_USERNAME": "someone"}):
                self.assertEqual(self.client.get("/api/v1/login/test-token", headers=headers).status_code, 401)
            with mock.patch.dict(os.environ, {"LOCAL_VIEWER_PASSWORD": ""}):
                self.assertEqual(self.client.get("/api/v1/login/test-token", headers=headers).status_code, 401,
                                 "Nor does a token outlive its account.")

    def test_a_refresh_keeps_the_account(self):
        refresh_token = self._sign_in().json()["refresh_token"]
        response = self.client.post("/api/v1/login/refresh", headers={"Authorization": "Bearer " + refresh_token})
        self.assertEqual(response.status_code, 200)
        access = {"Authorization": "Bearer " + response.json()["access_token"]}
        body = self.client.get("/api/v1/login/test-token", headers=access).json()
        self.assertEqual((body["username"], body["hub_access"]), ("viewer", False))

    def test_a_token_issued_before_the_local_viewer_existed_is_the_administrators(self):
        """
        Every token named the local administrator then, and named no role.
        """
        token = login.generate_local_token(username="admin", secret_key="secret", minutes_valid=15, aud="access")
        payload = deps.verify_local_token(token, aud="access")
        self.assertEqual(payload["role"], deps.LOCAL_ADMINISTRATOR)
        legacy = token_without_role("admin")
        caller = deps.get_identity(token=legacy)
        self.assertTrue(caller.unrestricted)

    def test_a_password_that_is_not_ascii_signs_in(self):
        """
        It raised a TypeError in the comparison - a 500 instead of a sign-in.
        """
        os.environ["LOCAL_VIEWER_PASSWORD"] = "Maschinenführer"
        self.assertEqual(self._sign_in("viewer", "Maschinenführer").status_code, 200)
        self.assertEqual(self._sign_in("viewer", "Maschinenfuhrer").status_code, 401)


def token_without_role(username: str) -> str:
    """
    A token as this app signed it before the local viewer existed.

    :param username: Its subject.
    :return: The token.
    """
    import datetime
    import hashlib
    import hmac
    import json

    header = deps._b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {"sub": username, "iss": "collectu-local", "aud": "access",
              "exp": int((datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)).timestamp())}
    payload = deps._b64encode(json.dumps(claims, separators=(",", ":")).encode())
    signature = hmac.new(b"secret", f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{deps._b64encode(signature)}"


if __name__ == '__main__':
    unittest.main()
