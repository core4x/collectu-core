"""
The command line of the app (utils.arg_parser).
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

# Internal imports.
import config
import data_layer
import utils.arg_parser
import utils.hub_connection
import utils.updater
from test.helpers import MODULES, GlobalStateTestCase

CHECKOUT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
"""The root of the checkout."""


class TestCommandLine(GlobalStateTestCase):

    def setUp(self):
        super().setUp()
        for name in ("send_modules", "download_modules", "update_modules"):
            patcher = mock.patch.object(utils.hub_connection, name)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(utils.updater, "update_app")
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _process(*arguments: str) -> tuple:
        """
        Process the given command line.

        :returns: The exit code (None if the app goes on), and what was written to stdout and to stderr.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        code = None
        with mock.patch.object(sys, "argv", ["main.py", *arguments]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                utils.arg_parser.process_commands()
            except SystemExit as e:
                code = e.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_without_arguments_the_app_goes_on(self):
        self.assertEqual(self._process(), (None, "", ""))

    def test_about(self):
        self.assertEqual(self._process("--about"), (0, f"{config.APP_NAME}\n{config.CONTACT}\n", ""))

    def test_the_modules_are_listed(self):
        data_layer.registered_modules.update(MODULES)

        code, stdout, _ = self._process("--modules", "outputs", "processors")

        self.assertEqual(code, 0)
        self.assertEqual(stdout.splitlines(), ["processors.test.multiplier_1: A processor of the tests.",
                                               "outputs.test.collector_1: An output of the tests.",
                                               "outputs.test.buffer_1: A buffer of the tests."])
        self.assertEqual(len(self._process("-m", "all")[1].splitlines()), len(MODULES))
        self.assertEqual(len(self._process("-m", "inputs")[1].splitlines()), 4)

    def test_cold_starts_the_api_without_a_configuration(self):
        self.assertEqual(self._process("--cold"), (None, "", ""))
        self.assertEqual((os.environ["API"], os.environ["FRONTEND"], os.environ["AUTO_START"]), ("1", "1", "0"))

    def test_run_starts_the_given_configuration_file(self):
        with mock.patch.object(utils.arg_parser.os.path, "isfile", return_value=True) as isfile:
            self.assertEqual(self._process("--run", "press.yml"), (None, "", ""))
        self.assertEqual(os.environ["CONFIG"], "press.yml")
        self.assertEqual(os.path.normpath(isfile.call_args.args[0]),
                         os.path.join(CHECKOUT, "configuration", "press.yml"))

    def test_run_without_a_filename_starts_the_default_configuration_file(self):
        with mock.patch.object(utils.arg_parser.os.path, "isfile", return_value=True):
            self._process("--run")
        self.assertEqual(os.environ["CONFIG"], "configuration.yml")

    def test_run_with_a_file_which_does_not_exist_exits(self):
        with mock.patch.object(utils.arg_parser.os.path, "isfile", return_value=False):
            code, _, stderr = self._process("--run", "missing.yml")
        self.assertEqual(code, 1)
        self.assertIn("'missing.yml' could not be found in the configuration directory", stderr)

    def test_the_commands_of_the_hub(self):
        cases = [(("--send_modules",), utils.hub_connection.send_modules, {"module_names": None}),
                 (("-s", "outputs.test.collector_1"), utils.hub_connection.send_modules,
                  {"module_names": ["outputs.test.collector_1"]}),
                 (("--download_modules", "official"), utils.hub_connection.download_modules,
                  {"requested_module_types": "official"}),
                 (("--update_modules",), utils.hub_connection.update_modules, {"module_names": None}),
                 (("-d", "outputs.test.collector_1"), utils.hub_connection.update_modules,
                  {"module_names": ["outputs.test.collector_1"]})]
        for arguments, function, expected in cases:
            with self.subTest(arguments=arguments):
                function.reset_mock()
                self.assertEqual(self._process(*arguments)[0], 0)
                function.assert_called_once_with(**expected)

    def test_update(self):
        self.assertEqual(self._process("--update")[0], 0)
        utils.updater.update_app.assert_called_once_with()

    def test_only_one_command_is_taken_at_a_time(self):
        code, _, stderr = self._process("--about", "--update")
        self.assertEqual(code, 2)
        self.assertIn("not allowed with argument", stderr)
        utils.updater.update_app.assert_not_called()

    def test_an_unknown_choice_is_refused(self):
        for arguments in (("--download_modules", "everything"), ("--modules", "sensors")):
            with self.subTest(arguments=arguments):
                code, _, stderr = self._process(*arguments)
                self.assertEqual(code, 2)
                self.assertIn("invalid choice", stderr)


if __name__ == '__main__':
    unittest.main()
