"""
Signing in to this app by approving it on the hub (`/login/hub/start`, `/login/hub/poll` of interface/api_v1/routers/v1/
login.py) - how every hub account signs in here, with a password or with Google, Microsoft or GitHub.

This app starts and collects the sign-in with its own token, holds the hub's secret for it in a cookie of the browser
that started it, and is handed a session of whoever approved - set as cookies, as the local administrator's are.

And the password form, which is the local administrator's alone: a hub password posted here is refused without
reaching the hub, so that it never crosses the factory network to a Core.
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

    import config
    import interface.api_v1.routers.deps as deps
    import interface.api_v1.routers.v1.login as login
    from interface.api_v1.routers.v1 import api_router
    from test.api.test_api_permissions import ENVIRONMENT, FakeResponse, VIEWER, hub

    api_available = True
except ImportError:
    api_available = False

STARTED: dict = {"device_code": "the-device-code", "user_code": "BCDF-GHJK",
                 "verification_uri": "https://collectu.de/sign-in/app",
                 "verification_uri_complete": "https://collectu.de/sign-in/app?code=BCDF-GHJK",
                 "expires_in": 600, "interval": 3}
"""What the hub answers a started sign-in with."""

SESSION: dict = {"access_token": "hub-access", "refresh_token": "hub-refresh", "token_type": "bearer"}
"""The session of whoever approved."""


class HubSignInTestCase(unittest.TestCase):
    """
    The routes of this app, with the hub stood in for: `answers` are what it answers next, `hub` the requests it was
    sent.
    """

    def setUp(self):
        patcher = mock.patch.dict(os.environ, ENVIRONMENT)
        patcher.start()
        self.addCleanup(patcher.stop)
        # What the hub answered about a caller is kept for a moment - not from one test to the next.
        deps.forget_identity()
        self.addCleanup(deps.forget_identity)
        # Who the session is, asked as after every sign-in.
        patcher = mock.patch.object(deps.session, "get", side_effect=hub(permissions=VIEWER))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.answers: list[FakeResponse] = []
        patcher = mock.patch.object(login.requests, "request", side_effect=lambda *args, **kwargs: self.answers.pop(0))
        self.hub = patcher.start()
        self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        self.client = TestClient(app, base_url="https://testserver")

    def _start(self):
        self.answers.append(FakeResponse(body=STARTED))
        return self.client.post("/api/v1/login/hub/start")

    def _poll(self, answer: dict):
        self.answers.append(FakeResponse(body=answer))
        return self.client.post("/api/v1/login/hub/poll")


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestHubSignIn(HubSignInTestCase):

    def test_the_page_is_shown_the_code_and_never_the_secret(self):
        response = self._start()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user_code"], "BCDF-GHJK")
        self.assertNotIn("device_code", response.json())
        cookie = response.headers["set-cookie"]
        self.assertIn("hub_sign_in=the-device-code", cookie)
        self.assertIn("HttpOnly", cookie)
        args, kwargs = self.hub.call_args
        self.assertEqual(args[1], config.HUB_APP_SIGN_IN_START_ADDRESS)
        self.assertEqual(kwargs["json"], {"app_id": ENVIRONMENT["APP_ID"]})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + ENVIRONMENT["HUB_API_ACCESS_TOKEN"])

    def test_the_session_of_whoever_approved_is_set_as_cookies(self):
        self._start()
        self.assertEqual(self._poll({"status": "pending"}).json(), {"status": "pending"})

        response = self._poll(SESSION)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["access_token"], "hub-access")
        self.assertEqual(self.client.cookies.get("access_token_cookie"), "hub-access")
        self.assertEqual(self.client.cookies.get("refresh_token_cookie"), "hub-refresh")
        self.assertIsNone(self.client.cookies.get("hub_sign_in"), "a sign-in is collected once")
        kwargs = self.hub.call_args.kwargs
        self.assertEqual(kwargs["json"], {"device_code": "the-device-code"})
        self.assertEqual(kwargs["cookies"]["device_id_cookie"], self.client.cookies.get("device_id_cookie"),
                         "the hub binds the session to this browser, which refreshes it")

    def test_a_denied_sign_in_has_to_be_started_again(self):
        self._start()

        self.assertEqual(self._poll({"status": "denied"}).json(), {"status": "denied"})
        self.assertIsNone(self.client.cookies.get("hub_sign_in"))
        self.assertEqual(self.client.post("/api/v1/login/hub/poll").json(), {"status": "expired"})

    def test_somebody_the_hub_does_not_let_see_this_app_is_refused(self):
        self._start()
        with mock.patch.object(deps.session, "get", side_effect=hub(permissions=VIEWER, app_owner_id=None)):
            response = self._poll(SESSION)

        self.assertNotEqual(response.status_code, 200)
        self.assertIsNone(self.client.cookies.get("access_token_cookie"))

    def test_an_app_without_a_hub_token_can_not_start_one(self):
        with mock.patch.dict(os.environ, {"HUB_API_ACCESS_TOKEN": ""}):
            response = self.client.post("/api/v1/login/hub/start")

        self.assertEqual(response.status_code, 409)
        self.hub.assert_not_called()


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestPasswordSignIn(HubSignInTestCase):
    """
    `/login/access-token`, which takes the local administrator's password and no other.
    """

    def _password(self, username: str = "someone@example.com", password: str = "the-hub-password"):
        return self.client.post("/api/v1/login/access-token", data={"username": username, "password": password})

    def test_the_local_administrator_signs_in_with_the_password(self):
        response = self._password(username="admin", password="password")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(self.client.cookies.get("access_token_cookie"))
        self.hub.assert_not_called()

    def test_a_hub_password_is_refused_and_passed_on_to_nobody(self):
        response = self._password()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], login.NOT_THE_LOCAL_ADMINISTRATOR)
        self.hub.assert_not_called()
        self.assertIsNone(self.client.cookies.get("access_token_cookie"))

    def test_a_wrong_password_of_the_local_administrator_is_refused(self):
        self.assertEqual(self._password(username="admin", password="wrong").status_code, 401)
        self.hub.assert_not_called()

    def test_without_a_local_administrator_password_nobody_signs_in_with_one(self):
        os.environ["LOCAL_ADMIN_PASSWORD"] = ""

        self.assertEqual(self._password(username="admin", password="anything").status_code, 401)
        self.hub.assert_not_called()

    def test_there_is_no_second_factor_to_relay(self):
        response = self.client.post("/api/v1/login/mfa", json={"mfa_token": "a-token", "code": "123456"})

        self.assertIn(response.status_code, (404, 405))
        self.hub.assert_not_called()

    def test_a_session_of_the_hub_keeps_refreshing_on_the_device_of_this_browser(self):
        self.answers.append(FakeResponse(body=SESSION))

        response = self.client.post("/api/v1/login/refresh",
                                    cookies={"refresh_token_cookie": "hub-refresh", "device_id_cookie": "the-device"})

        self.assertEqual(response.status_code, 200, response.text)
        args, kwargs = self.hub.call_args
        self.assertEqual(args[1], config.HUB_REFRESH_TOKEN_ADDRESS)
        self.assertEqual(kwargs["cookies"], {"refresh_token_cookie": "hub-refresh", "device_id_cookie": "the-device"})


if __name__ == "__main__":
    unittest.main()
