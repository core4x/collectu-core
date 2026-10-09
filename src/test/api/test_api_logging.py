"""
Where the logs of the server of the api go (interface/api_v1/app.py): uvicorn's, through the handlers of the app. The
logs of fastmcp, which only a server with MCP switched on runs on, are test_api_mcp's.
"""
import contextlib
import importlib
import logging
import os
import unittest
from unittest import mock

# Internal imports.
from test.helpers import records_reaching_the_app

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "app.py")):
        raise ImportError("The interface submodule is not checked out.")
    import fastapi
    import uvicorn

    api_available = True
except ImportError:
    # `interface` is a submodule, which CI does not check out, and FastAPI is among the submodule's requirements
    # rather than this repository's.
    api_available = False

UVICORN: tuple[str, ...] = ("uvicorn", "uvicorn.error", "uvicorn.access")
"""The loggers of uvicorn."""


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestStart(unittest.TestCase):
    """
    `start` runs uvicorn in a thread of its own - here, not at all.
    """

    @classmethod
    def setUpClass(cls):
        # The app mounts its static files by a path relative to src.
        with mock.patch.dict(os.environ, {"MCP": "0"}), contextlib.chdir(SRC):
            cls.api = importlib.import_module("interface.api_v1.app")

    def setUp(self):
        loggers = [logging.getLogger(name) for name in UVICORN]
        state = [(list(each.handlers), each.level, each.propagate) for each in loggers]
        self.addCleanup(self._restore, loggers, state)
        patcher = mock.patch.object(self.api.ServerThread, "run_in_thread")
        self.run_in_thread = patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _restore(loggers, state):
        for each, (handlers, level, propagate) in zip(loggers, state):
            each.handlers[:] = handlers
            each.setLevel(level)
            each.propagate = propagate

    def test_the_logs_of_uvicorn_reach_the_handlers_of_the_app(self):
        """
        Its loggers used to have no handlers and not to propagate, so the traceback of a route that raised showed on
        the console of the machine and nowhere else - not in the log file, not in the reports.
        """
        reached = records_reaching_the_app(self, "uvicorn")

        self.api.start()
        logging.getLogger("uvicorn.error").error("Exception in ASGI application")
        logging.getLogger("uvicorn.access").info('127.0.0.1:50000 - "GET /api/v1/log HTTP/1.1" 200')

        self.run_in_thread.assert_called_once()
        self.assertEqual([(record.name, record.getMessage()) for record in reached],
                         [("uvicorn.error", "Exception in ASGI application")],
                         "Once, and without the access log, which is at INFO.")


if __name__ == '__main__':
    unittest.main()
