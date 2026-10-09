"""
The mcp server of this app (interface/api_v1/app.py): the routes opted in by their tags, as tools, each called in
process with the token the server was called with - which fastmcp strips from what it forwards since version 3, and
`forward_authorization` hands on. And the logs of fastmcp, which go where the app's own do.
"""
import asyncio
import contextlib
import importlib
import logging
import os
import sys
import unittest
from unittest import mock

# Internal imports.
import config
from test.helpers import records_reaching_the_app

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "app.py")):
        raise ImportError("The interface submodule is not checked out.")
    import fastmcp
    import httpx2
    from fastmcp.client.transports import StreamableHttpTransport

    import interface.api_v1.routers.v1.login as login

    mcp_available = True
except ImportError:
    # `interface` is a submodule, which CI does not check out, and fastmcp is an optional requirement of it
    # (requirements-mcp.txt), installed only where the mcp server is switched on.
    mcp_available = False

ENVIRONMENT: dict[str, str] = {"API_AUTHENTICATION": "1",
                               "LOCAL_ADMIN_USERNAME": "admin",
                               "LOCAL_ADMIN_PASSWORD": "password",
                               "LOCAL_ADMIN_SECRET_KEY": "secret"}
"""Authentication switched on, and a local administrator to call the server as - whose token needs no hub."""


@unittest.skipUnless(mcp_available, "The interface submodule, FastAPI or fastmcp is not available.")
class TestMCPServer(unittest.TestCase):
    """
    A client connects to the server where this app serves it, lists its tools and calls one - once with a token and
    once without. Once, for all tests: the session manager of the server runs only once.
    """

    @classmethod
    def setUpClass(cls):
        # The server is built on import, if MCP is switched on then - so afresh, should a test before have imported the
        # app without. The app mounts its static files by a path relative to src.
        sys.modules.pop("interface.api_v1.app", None)
        with mock.patch.dict(os.environ, {"MCP": "1"}), mock.patch.object(config, "MCP_ALL_AS_TOOL", True), \
                contextlib.chdir(SRC):
            cls.api = importlib.import_module("interface.api_v1.app")
        with mock.patch.dict(os.environ, ENVIRONMENT):
            cls.tools, cls.signed_in, cls.anonymous = asyncio.run(cls._session())

    @classmethod
    async def _session(cls):
        """
        :returns: The tools listed, and what `get_logs` answered with the local administrator's token and without one.
        """

        def asgi_client(**kwargs) -> httpx2.AsyncClient:
            return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=cls.api.app), **kwargs)

        def client(headers: dict[str, str]) -> fastmcp.Client:
            return fastmcp.Client(StreamableHttpTransport("https://testserver" + cls.api.MCP_PREFIX + "/",
                                                          headers=headers, httpx_client_factory=asgi_client))

        token = login.generate_local_token(username="admin", secret_key="secret", minutes_valid=15, aud="access")
        async with cls.api.app.router.lifespan_context(cls.api.app):
            async with client({"Authorization": "Bearer " + token}) as signed_in:
                tools = await signed_in.list_tools()
                logs = await signed_in.call_tool("get_logs", {}, raise_on_error=False)
            async with client({}) as anonymous:
                refused = await anonymous.call_tool("get_logs", {}, raise_on_error=False)
        return tools, logs, refused

    @staticmethod
    def _text(result) -> str:
        return " ".join(getattr(block, "text", "") for block in result.content)

    def test_the_routes_opted_in_are_its_tools(self):
        """
        The routes tagged for it, and nothing else of the api.
        """
        opted_in = {operation["operationId"]
                    for path_item in self.api.app.openapi()["paths"].values()
                    for operation in path_item.values()
                    if isinstance(operation, dict) and self.api.MCP_TAGS & set(operation.get("tags", []))}
        self.assertTrue(opted_in)
        self.assertEqual({tool.name for tool in self.tools}, opted_in)

    def test_a_tool_calls_the_api_with_the_token_the_server_was_called_with(self):
        """
        Without it, the route answers 401 to the local administrator as to anybody else.
        """
        self.assertFalse(self.signed_in.is_error, self._text(self.signed_in))

    def test_a_tool_called_without_a_token_is_refused_by_its_route(self):
        self.assertTrue(self.anonymous.is_error)
        self.assertIn("401", self._text(self.anonymous))

    def test_the_logs_of_fastmcp_reach_the_handlers_of_the_app_once(self):
        """
        fastmcp sets up a handler of its own on import, printing to stderr with rich, which would write each of its
        records a second time.
        """
        for name in ("fastmcp", "mcp"):
            with self.subTest(logger=name):
                reached = records_reaching_the_app(self, name)

                logging.getLogger(name + ".server").warning("Session not found.")

                self.assertEqual([record.name for record in reached], [name + ".server"])
                self.assertEqual(logging.getLogger(name).handlers, [])


if __name__ == '__main__':
    unittest.main()
