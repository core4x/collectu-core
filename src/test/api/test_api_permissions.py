"""
What each route of the api takes, and how a caller's permissions are established.

The routes are this app's and the permissions collectu-hub-api's - see interface/api_v1/routers/deps.py. `EXPECTED`
below is the whole of what the routes take, in one place to review: a route added without saying what it takes fails
`test_every_route_says_what_it_takes` rather than being open, and one whose permissions change fails
`test_what_each_route_takes` until the table says so too.
"""
import http.client
import io
import os
import unittest
from unittest import mock

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "routers", "deps.py")):
        raise ImportError("The interface submodule is not checked out.")
    import requests
    from fastapi import FastAPI, HTTPException
    from fastapi.openapi.utils import get_openapi
    from fastapi.routing import APIRoute, iter_route_contexts
    from fastapi.testclient import TestClient

    import interface.api_v1.routers.deps as deps
    import interface.api_v1.routers.v1.hub_proxy as hub_proxy
    import interface.api_v1.routers.v1.login as login
    from interface.api_v1.routers.v1 import api_router

    P = deps.P
    api_available = True
except ImportError:
    # `interface` is a submodule, which CI does not check out, and FastAPI is among the submodule's requirements
    # rather than this repository's.
    api_available = False

APP_ID: str = "11111111-1111-1111-1111-111111111111"
"""The app the hub is asked about."""

OWNER_ID: str = "22222222-2222-2222-2222-222222222222"
"""Its owner at the hub."""

NO_CALLER: set[tuple[str, str]] = {
    ("GET", "/api/v1/capabilities"),
    ("GET", "/api/v1/version"),
    ("POST", "/api/v1/login/access-token"),
    ("POST", "/api/v1/login/mfa"),
    ("POST", "/api/v1/login/refresh"),
    ("POST", "/api/v1/logout"),
    # An app reports to a mothership, and fetches its tasks there, with nothing but its app id - as it does to the
    # hub, where that takes no permission either.
    ("POST", "/api/v1/app"),
    ("GET", "/api/v1/task/app_id/{app_id}"),
}
"""The routes that take no caller at all."""

EXPECTED: dict[tuple[str, str], list[str]] = {
    ("GET", "/api/v1/login/test-token"): [],
    # The apps reporting to this one, as on the hub.
    ("GET", "/api/v1/app"): ["app:read"],
    ("GET", "/api/v1/app/app_id/{app_id}"): ["app:read"],
    ("GET", "/api/v1/app/app_id/{app_id}/logs"): ["app:read"],
    ("GET", "/api/v1/app/app_id/{app_id}/installed_packages"): ["app:read"],
    ("GET", "/api/v1/app/app_id/{app_id}/configuration"): ["app:read"],
    ("DELETE", "/api/v1/app/app_id/{app_id}"): ["app:delete"],
    ("POST", "/api/v1/task"): ["task:create"],
    # The modules installed here.
    ("GET", "/api/v1/module"): ["module:read"],
    ("GET", "/api/v1/module/{module_name}/code"): ["module:read"],
    ("GET", "/api/v1/processor"): ["module:read"],
    ("GET", "/api/v1/configuration/options"): ["module:read"],
    ("POST", "/api/v1/module"): ["module:create", "module:update"],
    ("POST", "/api/v1/module/publish"): ["module:create", "module:update"],
    ("POST", "/api/v1/module/download"): ["module:create", "module:update"],
    ("POST", "/api/v1/module/update"): ["module:update"],
    # This app itself: what it runs, what passes through it, how it is doing.
    ("GET", "/api/v1/configuration/current"): ["app:read"],
    ("GET", "/api/v1/module/data"): ["app:read"],
    ("GET", "/api/v1/module/data/stream"): ["app:read"],
    ("GET", "/api/v1/module/data/{id}"): ["app:read"],
    ("GET", "/api/v1/dashboard/stream"): ["app:read"],
    ("GET", "/api/v1/log"): ["app:read"],
    ("GET", "/api/v1/log/stream"): ["app:read"],
    ("GET", "/api/v1/metric"): ["app:read"],
    ("GET", "/api/v1/metric/stream"): ["app:read"],
    ("GET", "/api/v1/update/commits"): ["app:read"],
    ("GET", "/api/v1/settings"): ["app:update"],
    ("PUT", "/api/v1/settings"): ["app:update"],
    # Its commands, which the hub sends as tasks.
    ("POST", "/api/v1/configuration/module/start"): ["task:create"],
    ("POST", "/api/v1/configuration/module/stop"): ["task:create"],
    ("POST", "/api/v1/configuration/start"): ["task:create"],
    ("POST", "/api/v1/configuration/start_from_file"): ["task:create"],
    ("POST", "/api/v1/configuration/stop"): ["task:create"],
    ("POST", "/api/v1/configuration/save"): ["task:create"],
    ("POST", "/api/v1/processor/run"): ["task:create"],
    ("POST", "/api/v1/update/restart"): ["task:create"],
    ("POST", "/api/v1/update"): ["task:create"],
    # Its input forms, which whoever may see it may use.
    ("GET", "/api/v1/user_input"): ["app:read"],
    ("POST", "/api/v1/user_input"): ["app:read"],
    # The configurations saved here.
    ("GET", "/api/v1/configuration"): ["configuration:read"],
    ("GET", "/api/v1/configuration/{id}"): ["configuration:read"],
    ("POST", "/api/v1/configuration"): ["configuration:create"],
    ("PUT", "/api/v1/configuration/{id}"): ["configuration:update"],
    ("DELETE", "/api/v1/configuration/{id}"): ["configuration:delete"],
    # The hub, whose own route decides (see test_hub_proxy below).
    ("GET", "/api/v1/hub_proxy/{path}"): [],
    ("POST", "/api/v1/hub_proxy/{path}"): [],
    ("PUT", "/api/v1/hub_proxy/{path}"): [],
    ("DELETE", "/api/v1/hub_proxy/{path}"): [],
}
"""What each route that takes a caller takes."""

VIEWER: list[str] = ["app:read", "module:read", "configuration:read", "task:read", "mqtt:subscribe", "ai:use"]
"""Some of what a viewer holds at the hub."""


class FakeResponse:
    """A response of requests, as far as the code under test reads one."""

    def __init__(self, status_code: int = 200, body=None, raw: bytes | None = None):
        self.status_code = status_code
        self._body = body
        self._raw = raw
        self.headers = {"Content-Type": "application/json"}
        self.content = raw if raw is not None else b"{}"

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self):
        if self._raw is not None:
            raise ValueError("Not json.")
        return self._body

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(response=self)


def hub(permissions: list[str], owner_id: str = OWNER_ID, app_owner_id: str | None = OWNER_ID, calls=None):
    """
    A stand-in for the hub's answers about a caller.

    :param permissions: What /role/effective answers.
    :param owner_id: The owner /role/effective answers about.
    :param app_owner_id: The owner the app lookup answers.
    :param calls: A list to record each request's (url, params, headers) in.
    :return: A replacement for the session's `get`.
    """

    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, params, dict(headers or {})))
        if url.endswith("/app/app_id/" + APP_ID):
            return FakeResponse(body={"app_id": APP_ID, "owner_id": app_owner_id})
        if url.endswith("/role/effective"):
            return FakeResponse(body={"owner_id": owner_id, "permissions": permissions})
        if url.endswith("/login/test-token"):
            return FakeResponse(body={"username": "alice"})
        return FakeResponse(status_code=404, body={"detail": "Not Found"})

    return get


HUB_TOKEN: str = "hub-token"
"""The token a caller with a hub account came with."""


def identity(*permissions: str):
    """
    A caller with a hub account, holding the given permissions.

    :param permissions: What the hub answered.
    :return: The identity.
    """
    return deps._identity(username="", held=permissions, unrestricted=False, authentication_required=True,
                          owner_id=OWNER_ID, hub_token=HUB_TOKEN)


def local_administrator():
    """
    The local administrator, who has no hub account.

    :return: The identity.
    """
    return deps._identity(username="admin", held=(), unrestricted=True, authentication_required=True)


def local_token(username: str = "admin", secret_key: str = "secret", aud: str = "access") -> str:
    """
    A token this app signs for its local administrator.
    """
    return login.generate_local_token(username=username, secret_key=secret_key, minutes_valid=15, aud=aud)


ENVIRONMENT: dict[str, str] = {"API_AUTHENTICATION": "1",
                               "APP_ID": APP_ID,
                               "LOCAL_ADMIN_USERNAME": "admin",
                               "LOCAL_ADMIN_PASSWORD": "password",
                               "LOCAL_ADMIN_SECRET_KEY": "secret",
                               "HUB_API_ACCESS_TOKEN": "the-apps-own-token"}
"""The environment every test runs in, unless it says otherwise."""


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestRouteDeclarations(unittest.TestCase):
    """
    What the routes say they take - which is what they check, since `requires` is both.
    """

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        # Not `app.routes`, which holds an included router as one entry of its own since FastAPI 0.14x.
        cls.routes = [route for route in iter_route_contexts(app.routes) if isinstance(route.original_route, APIRoute)]
        schema = deps.document_permissions(get_openapi(title="test", version="1", routes=app.routes))
        cls.declared = {(method.upper(), path): operation.get(deps.PERMISSIONS_EXTENSION)
                        for path, item in schema["paths"].items() for method, operation in item.items()}

    def test_every_route_says_what_it_takes(self):
        """
        Every route either takes a caller, through exactly one `requires`, or is listed as taking none. A second
        `requires` would ask the hub a second time for the same request.
        """
        checked = set()
        for route in self.routes:
            for method in route.methods:
                # `path_format`, as the OpenAPI document names it: `{path}` rather than `{path:path}`.
                checked.add((method, route.path_format))
                with self.subTest(method=method, path=route.path_format):
                    count = _count(route.dependant, deps.authorize)
                    self.assertEqual(count, 0 if (method, route.path_format) in NO_CALLER else 1)
        self.assertEqual(checked, set(EXPECTED) | NO_CALLER, "Every route was checked, and only those.")

    def test_what_each_route_takes(self):
        self.assertEqual(set(self.declared), set(EXPECTED) | NO_CALLER,
                         "A route is missing from EXPECTED or NO_CALLER, or listed there without existing.")
        for key, permissions in EXPECTED.items():
            with self.subTest(route=key):
                self.assertEqual(self.declared[key], permissions)
        for key in NO_CALLER:
            with self.subTest(route=key):
                self.assertIsNone(self.declared[key])

    def test_every_permission_taken_is_one_this_app_names(self):
        named = {permission.value for permission in P}
        for key, permissions in self.declared.items():
            for permission in permissions or []:
                with self.subTest(route=key):
                    self.assertIn(permission, named)


def _count(dependant, call) -> int:
    """
    How often a dependency is part of a route.

    :param dependant: The route's dependant.
    :param call: The dependency.
    :return: The number of times it is.
    """
    return sum((dependency.call is call) + _count(dependency, call) for dependency in dependant.dependencies)


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestIdentity(unittest.TestCase):
    """
    Who a caller is, and what they may do - `deps.get_identity`.
    """

    def setUp(self):
        patcher = mock.patch.dict(os.environ, ENVIRONMENT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _hub(self, **kwargs):
        patcher = mock.patch.object(deps.session, "get", side_effect=hub(**kwargs))
        get = patcher.start()
        self.addCleanup(patcher.stop)
        return get

    def test_without_authentication_anybody_may_do_everything(self):
        os.environ["API_AUTHENTICATION"] = "0"
        caller = deps.get_identity(token=None)
        self.assertTrue(caller.unrestricted)
        self.assertFalse(caller.authentication_required)
        self.assertEqual(caller.permissions, [permission.value for permission in P])

    def test_a_request_without_a_token_is_refused(self):
        with self.assertRaises(HTTPException) as refused:
            deps.get_identity(token=None)
        self.assertEqual(refused.exception.status_code, 401)

    def test_the_local_administrator_may_do_everything(self):
        get = self._hub(permissions=[])
        caller = deps.get_identity(token=local_token())
        self.assertTrue(caller.unrestricted)
        self.assertEqual(caller.username, "admin")
        self.assertEqual(caller.permissions, [permission.value for permission in P])
        self.assertIsNone(caller.hub_token, "No hub account: this app's own token acts at the hub for it.")
        self.assertIsNone(caller.owner_id, "...which acts for the owner of this app by itself.")
        get.assert_not_called()

    def test_a_local_token_is_never_verified_with_an_empty_key(self):
        """
        Before the local administrator first signs in, no key exists - and one that is empty verifies a signature
        anybody can compute.
        """
        os.environ["LOCAL_ADMIN_SECRET_KEY"] = ""
        self.assertIsNone(deps.verify_local_token(local_token(secret_key=""), aud="access"))

    def test_a_local_token_signs_in_only_the_local_administrator_there_is(self):
        token = local_token()
        self.assertIsNotNone(deps.verify_local_token(token, aud="access"))
        self.assertIsNone(deps.verify_local_token(token, aud="refresh"))
        with mock.patch.dict(os.environ, {"LOCAL_ADMIN_USERNAME": "somebody-else"}):
            self.assertIsNone(deps.verify_local_token(token, aud="access"))
        with mock.patch.dict(os.environ, {"LOCAL_ADMIN_PASSWORD": ""}):
            self.assertIsNone(deps.verify_local_token(token, aud="access"))

    def test_a_hub_caller_may_do_what_the_hub_answers(self):
        self._hub(permissions=VIEWER + ["configuration:create"])
        caller = deps.get_identity(token="hub-token")
        self.assertFalse(caller.unrestricted)
        self.assertEqual(caller.permissions,
                         ["app:read", "module:read", "configuration:read", "configuration:create"],
                         "What the hub answered of this app's permissions, in their order.")
        self.assertEqual(caller.owner_id, OWNER_ID)
        self.assertEqual(caller.hub_token, "hub-token", "What this app does at the hub for it, it does with this.")
        self.assertTrue(caller.has(P.APP_READ))
        self.assertFalse(caller.has(P.TASK_CREATE))
        with self.assertRaises(HTTPException) as refused:
            caller.require(P.TASK_CREATE, P.APP_READ, P.CONFIGURATION_DELETE)
        self.assertEqual(refused.exception.status_code, 403)
        self.assertEqual(refused.exception.detail,
                         "Not enough permissions: task:create, configuration:delete are required.")

    def test_the_hub_is_asked_about_the_owner_of_this_app(self):
        calls = []
        self._hub(permissions=VIEWER, calls=calls)
        deps.get_identity(token="hub-token")
        (app_url, _, _), (effective_url, effective_params, _) = calls
        self.assertTrue(app_url.endswith("/app/app_id/" + APP_ID))
        self.assertTrue(effective_url.endswith("/role/effective"))
        self.assertEqual(effective_params, {"owner_id": OWNER_ID})

    def test_each_caller_is_asked_about_with_their_own_token(self):
        """
        The session is shared by every caller. The token used to be written into its headers and read back by the
        request after, so two callers at once could be answered for each other's tokens.
        """
        calls = []
        self._hub(permissions=VIEWER, calls=calls)
        deps.get_identity(token="first")
        deps.get_identity(token="second")
        self.assertEqual([headers["Authorization"] for _, _, headers in calls],
                         ["Bearer first", "Bearer first", "Bearer second", "Bearer second"])
        self.assertNotIn("Authorization", deps.session.headers)

    def test_no_cookie_of_one_callers_answer_is_sent_for_the_next(self):
        """
        Stored the way requests stores what a response sets - and a plain session does store this one.
        """
        headers = http.client.parse_headers(io.BytesIO(b"Set-Cookie: session=of-the-first-caller; Path=/\r\n\r\n"))
        request = requests.Request("GET", "https://api.collectu.de/api/v1/role/effective").prepare()
        deps.session.cookies.extract_cookies(requests.cookies.MockResponse(headers),
                                             requests.cookies.MockRequest(request))
        self.assertEqual(len(deps.session.cookies), 0)

    def test_an_answer_about_another_owner_is_not_taken(self):
        self._hub(permissions=VIEWER, owner_id="33333333-3333-3333-3333-333333333333")
        with self.assertRaises(HTTPException) as refused:
            deps.get_identity(token="hub-token")
        self.assertEqual(refused.exception.status_code, 502)

    def test_an_app_without_an_owner_is_not_asked_about(self):
        """
        Asked without an owner, the hub answers for the caller's own account instead - somebody's permissions, but not
        on the owner of this app.
        """
        calls = []
        self._hub(permissions=VIEWER, app_owner_id=None, calls=calls)
        with self.assertRaises(HTTPException) as refused:
            deps.get_identity(token="hub-token")
        self.assertEqual(refused.exception.status_code, 502)
        self.assertEqual(len(calls), 1)

    def test_what_went_wrong_at_the_hub_is_answered_as_what_it_is(self):
        cases = [(FakeResponse(status_code=401, body={}), 401),
                 (FakeResponse(status_code=403, body={}), 403),
                 (FakeResponse(status_code=404, body={}), 403),
                 (FakeResponse(status_code=500, body={}), 502),
                 (FakeResponse(raw=b"<html>Bad Gateway</html>"), 502),
                 (requests.ConnectionError(), 503)]
        for answer, status_code in cases:
            with self.subTest(answer=answer), \
                    mock.patch.object(deps.session, "get", side_effect=[answer]):
                with self.assertRaises(HTTPException) as refused:
                    deps.get_identity(token="hub-token")
                self.assertEqual(refused.exception.status_code, status_code)

    def test_switching_authentication_takes_effect_without_a_restart(self):
        """
        Which requests are refused used to be decided once, on import: an app started without authentication read no
        token after it was switched on, and one started with it refused every request after it was switched off.
        """
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        client = TestClient(app, base_url="https://testserver")

        os.environ["API_AUTHENTICATION"] = "0"
        self.assertEqual(client.get("/api/v1/login/test-token").status_code, 200)
        os.environ["API_AUTHENTICATION"] = "1"
        self.assertEqual(client.get("/api/v1/login/test-token").status_code, 401)
        signed_in = client.get("/api/v1/login/test-token", headers={"Authorization": "Bearer " + local_token()})
        self.assertEqual(signed_in.status_code, 200)
        self.assertEqual(signed_in.json()["username"], "admin")
        os.environ["API_AUTHENTICATION"] = "0"
        self.assertEqual(client.get("/api/v1/login/test-token").status_code, 200)


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestEnforcement(unittest.TestCase):
    """
    A route refuses a caller that lacks what it takes, before anything of it runs.
    """

    def setUp(self):
        patcher = mock.patch.dict(os.environ, ENVIRONMENT)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = FastAPI()
        self.app.include_router(api_router, prefix="/api/v1")
        self.client = TestClient(self.app, base_url="https://testserver")

    def _as(self, caller):
        self.app.dependency_overrides[deps.get_identity] = lambda: caller

    def test_a_caller_without_the_permission_is_refused_before_the_route_runs(self):
        self._as(identity(*VIEWER))
        with mock.patch("utils.updater.restart_application") as restart:
            response = self.client.post("/api/v1/update/restart")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Not enough permissions: task:create is required.")
        restart.assert_not_called()

        response = self.client.delete("/api/v1/configuration/some-id")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Not enough permissions: configuration:delete is required.")

    def test_a_caller_with_the_permission_is_let_through(self):
        """
        An operator may command the app, as it may from the hub - which it could not while every command took the
        right to create, change and delete configurations.
        """
        self._as(identity(*VIEWER, "task:create"))
        with mock.patch("utils.updater.restart_application") as restart:
            response = self.client.post("/api/v1/update/restart")
        self.assertEqual(response.status_code, 204)
        restart.assert_called_once()

    def test_test_token_shows_what_the_caller_may_do(self):
        self._as(identity("configuration:read", "configuration:create", "ai:use"))
        with mock.patch.object(deps.session, "get", side_effect=hub(permissions=[])):
            response = self.client.get("/api/v1/login/test-token")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["username"], "alice")
        self.assertEqual(body["permissions"], ["configuration:read", "configuration:create"])
        self.assertEqual(body["owner_id"], OWNER_ID, "What a client names as the owner of what it does at the hub.")

    def test_whoever_may_see_the_app_may_use_its_input_forms(self):
        """
        Whatever else they may do: entering data is what the forms are for.
        """
        self._as(identity("app:read"))
        self.assertEqual(self.client.get("/api/v1/user_input").status_code, 200)
        response = self.client.post("/api/v1/user_input",
                                    json={"module_id": "no-such-module", "measurement": "m", "fields": {}, "tags": {}})
        self.assertEqual(response.status_code, 404, "Past the permissions, and refused for want of the module.")


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestHubProxy(unittest.TestCase):
    """
    What a caller does at the hub through this app, it does with its own hub token: the hub decides, and nobody does
    more or less through this app than at the hub itself. Only a caller without a hub account goes with this app's.
    """

    def setUp(self):
        patcher = mock.patch.dict(os.environ, ENVIRONMENT)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(hub_proxy.requests, "request", return_value=FakeResponse(body={}))
        self.forward = patcher.start()
        self.addCleanup(patcher.stop)

    def _proxy(self, caller, method: str, path: str):
        request = mock.Mock(method=method, client=mock.Mock(host="10.0.0.1"), query_params={})
        return hub_proxy.proxy_request(path=path, request=request, body=b"", identity=caller)

    def _sent_with(self) -> str:
        return self.forward.call_args.kwargs["headers"]["Authorization"]

    def test_a_caller_with_a_hub_account_acts_with_its_own_token(self):
        """
        It used to go with this app's token, whoever asked - and could do whatever that token may.
        """
        self._proxy(identity(*VIEWER), "POST", "task")
        self.assertEqual(self._sent_with(), "Bearer " + HUB_TOKEN)

    def test_a_caller_with_a_hub_account_needs_no_token_of_this_app(self):
        del os.environ["HUB_API_ACCESS_TOKEN"]
        self._proxy(identity(*VIEWER), "GET", "module/my")
        self.assertEqual(self._sent_with(), "Bearer " + HUB_TOKEN)

    def test_the_hubs_refusal_reaches_the_caller_as_it_is(self):
        """
        It names what the caller lacks. It used to become `403 Client Error: Forbidden for url: ...` instead.
        """
        refusal = b'{"detail":"Not enough permissions: task:create is required."}'
        self.forward.return_value = FakeResponse(status_code=403, raw=refusal)
        response = self._proxy(identity(*VIEWER), "POST", "task")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.body, refusal)

    def test_the_local_administrator_acts_with_this_apps_token(self):
        self._proxy(local_administrator(), "GET", "module/my")
        self.assertEqual(self._sent_with(), "Bearer the-apps-own-token")

    def test_without_any_token_nothing_is_sent(self):
        del os.environ["HUB_API_ACCESS_TOKEN"]
        with self.assertRaises(HTTPException) as refused:
            self._proxy(local_administrator(), "GET", "module/my")
        self.assertEqual(refused.exception.status_code, 400)
        self.forward.assert_not_called()

    def test_the_path_is_forwarded_as_it_was_asked_for(self):
        """
        Quoted, so a '#' or '?' in it does not start the fragment or the query on the way out.
        """
        self._proxy(identity("mqtt:subscribe"), "GET", "mqtt/subscribe/plant/line 1/#")
        self.assertTrue(self.forward.call_args.kwargs["url"].endswith("/mqtt/subscribe/plant/line%201/%23"))


if __name__ == '__main__':
    unittest.main()
