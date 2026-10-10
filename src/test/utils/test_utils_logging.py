"""
The logging of the app (utils.logging): where log records go, and what of them is kept for the reports.
"""
import logging
import logging.handlers
import socket
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

# Internal imports.
import config
import data_layer
import utils.logging
from test.helpers import GlobalStateTestCase, records_reaching_the_app


def _record(name: str = "collectu.outputs.test.collector_1.collector", level: int = logging.ERROR,
            message: str = "Disk full.", exc_info=None, args=None) -> logging.LogRecord:
    """
    A log record, as the logger of the output module 'collector' (outputs/test/collector_1.py) writes it.
    """
    return logging.LogRecord(name=name, level=level, pathname="/collectu/src/modules/outputs/test/collector_1.py",
                             lineno=1, msg=message, args=args, exc_info=exc_info)


class TestLoggingTrigger(GlobalStateTestCase):
    """
    Log records are kept as data objects: the latest ones of the app for the reports, and the latest one of each
    module for the editor.
    """

    def setUp(self):
        super().setUp()
        self.trigger = utils.logging.LoggingTrigger(levels=["INFO", "WARNING", "ERROR", "CRITICAL"])

    def test_a_record_is_kept_as_a_data_object(self):
        self.trigger.emit(_record())

        (log,) = data_layer.latest_logs
        self.assertEqual(log.measurement, "Logs")
        self.assertEqual(log.fields, {"level": "ERROR", "message": "Disk full.", "name": "collector",
                                      "module": "outputs.test.collector_1"})
        self.assertEqual(log.tags, {"level": "ERROR", "hostname": socket.gethostname(), "name": "collector",
                                    "module": "outputs.test.collector_1"})

    def test_the_arguments_of_a_record_are_filled_in(self):
        """
        Third party loggers pass the arguments of a message separately, so the template alone reads
        'HTTP Request: %s %s'.
        """
        self.trigger.emit(_record(message="HTTP Request: %s %s", args=("GET", "https://api.collectu.de")))
        self.assertEqual(data_layer.latest_logs[-1].fields["message"], "HTTP Request: GET https://api.collectu.de")

    def test_a_record_whose_arguments_do_not_fit_is_kept_unformatted(self):
        self.trigger.emit(_record(message="%s and %s", args=("one",)))
        self.assertEqual(data_layer.latest_logs[-1].fields["message"], "%s and %s")

    def test_the_record_is_the_latest_log_of_its_module(self):
        data_layer.module_data["collector"] = SimpleNamespace(latest_log=None)
        self.trigger.emit(_record())
        self.assertIs(data_layer.module_data["collector"].latest_log, data_layer.latest_logs[-1])

    def test_only_records_of_the_given_levels_are_kept(self):
        self.trigger.emit(_record(level=logging.DEBUG))
        self.assertEqual(len(data_layer.latest_logs), 0)

    def test_the_traceback_is_kept(self):
        record = _record()
        record.exc_text = "Traceback (most recent call last): ..."
        self.trigger.emit(record)
        self.assertEqual(data_layer.latest_logs[-1].fields["stacktrace"], "Traceback (most recent call last): ...")

    def test_only_the_latest_records_are_kept(self):
        for index in range(config.NUMBER_OF_BUFFERED_LOGS + 5):
            self.trigger.emit(_record(message=f"Message {index}."))
        self.assertEqual(len(data_layer.latest_logs), config.NUMBER_OF_BUFFERED_LOGS)
        self.assertEqual(data_layer.latest_logs[-1].fields["message"],
                         f"Message {config.NUMBER_OF_BUFFERED_LOGS + 4}.")


class TestTracebackInfoFilter(unittest.TestCase):
    """
    The console shows a traceback only with EXC_INFO, while the log file always gets it.
    """

    @staticmethod
    def _failed_record() -> logging.LogRecord:
        try:
            raise ValueError("Failed.")
        except ValueError:
            return _record(exc_info=sys.exc_info())

    def test_without_exc_info_the_traceback_is_hidden(self):
        record = self._failed_record()
        record.exc_text = "cached"
        with mock.patch.object(config, "EXC_INFO", False):
            self.assertTrue(utils.logging.TracebackInfoFilter().filter(record))
        self.assertEqual((record.exc_info, record.exc_text), (None, None))

    def test_with_exc_info_the_traceback_is_shown_again(self):
        record = self._failed_record()
        exc_info = record.exc_info
        with mock.patch.object(config, "EXC_INFO", False):
            utils.logging.TracebackInfoFilter().filter(record)
        with mock.patch.object(config, "EXC_INFO", True):
            self.assertTrue(utils.logging.TracebackInfoFilter().filter(record))
        self.assertIs(record.exc_info, exc_info)
        self.assertFalse(hasattr(record, "_exc_info_hidden"))


class TestStart(GlobalStateTestCase):
    """
    utils.logging.start sets up a file, the reports and the console as destinations.
    """

    def setUp(self):
        super().setUp()
        self.logger = logging.getLogger("collectu-test-logging")
        self.addCleanup(self._remove_handlers)
        self.patch_config(DEBUG=False)
        patcher = mock.patch.object(utils.logging, "TimedRotatingFileHandler",
                                    side_effect=lambda **kwargs: logging.NullHandler())
        self.file_handler = patcher.start()
        self.addCleanup(patcher.stop)

    def _remove_handlers(self):
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
        self.logger.setLevel(logging.NOTSET)

    def test_the_destinations_are_set_up(self):
        utils.logging.start(self.logger)

        file_handler, trigger, console = self.logger.handlers
        self.assertEqual(self.logger.level, logging.DEBUG)
        self.assertEqual(file_handler.level, logging.WARNING)
        self.assertTrue(self.file_handler.call_args.kwargs["filename"].endswith("Logs.log"))
        self.assertIsInstance(trigger, utils.logging.LoggingTrigger)
        self.assertEqual(trigger.levels, ["INFO", "WARNING", "ERROR", "CRITICAL"])
        self.assertIsInstance(console, logging.StreamHandler)
        self.assertEqual(console.level, logging.INFO)
        self.assertTrue(any(isinstance(item, utils.logging.TracebackInfoFilter) for item in console.filters))
        self.assertEqual(data_layer.latest_logs[-1].fields["message"], "Successfully created logger.")

    def test_debug_messages_are_shown_with_debug(self):
        self.patch_config(DEBUG=True)
        utils.logging.start(self.logger)
        _, trigger, console = self.logger.handlers
        self.assertIn("DEBUG", trigger.levels)
        self.assertEqual(console.level, logging.DEBUG)

    def test_the_app_stops_without_logging(self):
        with mock.patch.object(utils.logging.os, "makedirs", side_effect=PermissionError("Read-only.")), \
                self.assertLogs(self.logger, level="CRITICAL"):
            with self.assertRaises(SystemExit) as raised:
                utils.logging.start(self.logger)
        self.assertEqual(raised.exception.code, 1)


class TestAdopt(unittest.TestCase):
    """
    The loggers of a package the app runs on - uvicorn's, fastmcp's - log through the handlers of the app.
    """

    def setUp(self):
        self.package = logging.getLogger("collectu-test-package")
        self.addCleanup(self._reset)
        # What fastmcp sets up on import: a handler of its own, and no propagation.
        self.own_handler = logging.handlers.BufferingHandler(capacity=100)
        self.package.addHandler(self.own_handler)
        self.package.propagate = False

    def _reset(self):
        self.package.handlers.clear()
        self.package.setLevel(logging.NOTSET)
        self.package.propagate = True

    def test_a_record_reaches_the_handlers_of_the_app_once(self):
        utils.logging.adopt(self.package.name)
        reached = records_reaching_the_app(self, self.package.name)

        logging.getLogger("collectu-test-package.server").warning("Invalid HTTP request received.")

        self.assertEqual([record.getMessage() for record in reached], ["Invalid HTTP request received."])
        self.assertEqual(self.own_handler.buffer, [], "Removed, or the record would be written a second time.")

    def test_below_its_level_nothing_is_logged(self):
        """
        uvicorn logs every request it answers, at INFO.
        """
        utils.logging.adopt(self.package.name)
        reached = records_reaching_the_app(self, self.package.name)

        logging.getLogger("collectu-test-package.access").info('127.0.0.1:50000 - "GET /api/v1/log HTTP/1.1" 200')

        self.assertEqual(reached, [])


if __name__ == '__main__':
    unittest.main()
