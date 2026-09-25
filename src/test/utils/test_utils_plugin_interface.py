"""
Rendering a module's docstring into the payload `GET /modules/` returns, and installing the
third-party requirements of a module.
"""
import os
import subprocess
import sys
import types
import unittest
from unittest import mock

# Internal imports.
import utils.plugin_interface

try:
    import markdown
except ImportError:
    markdown = None

try:
    import uv
except ImportError:
    uv = None

DOCSTRING = """
Sign of life module.

| Key | Default |
|---|---|
| interval | 60 |

```json
{"fields": {"status": 1}}
```
"""


def module_class(name: str, docstring: str | None):
    """
    Builds a throwaway module with the given docstring and a class defined "in" it.

    `get_all_modules` reads the docstring off `sys.modules[cls.__module__]`, so the test
    has to register a real module object rather than pass a string.
    """
    module = types.ModuleType(name)
    module.__doc__ = docstring
    sys.modules[name] = module
    return type("Module", (), {"__module__": name})


class TestUtilsPluginInterface(unittest.TestCase):
    """
    This is the test for utils.plugin_interface.
    """

    def tearDown(self):
        """
        This method is called after each test.
        """
        for name in ("collectu_test_documented", "collectu_test_bare"):
            sys.modules.pop(name, None)

    def test_module_docstring_returns_the_docstring(self):
        """
        A documented module gives back exactly what it wrote.
        """
        cls = module_class("collectu_test_documented", DOCSTRING)
        self.assertEqual(DOCSTRING, utils.plugin_interface.module_docstring(cls),
                         "The docstring was not returned unchanged.")

    def test_module_docstring_returns_empty_string_without_one(self):
        """
        The crash case: no docstring must be "", never None.
        """
        cls = module_class("collectu_test_bare", None)
        result = utils.plugin_interface.module_docstring(cls)
        self.assertEqual("", result, "A module without a docstring should give an empty string.")
        self.assertIsInstance(result, str, "The result must be a string, never None.")

    @unittest.skipIf(markdown is None, "The optional markdown package is not installed.")
    def test_tables_and_fences_are_converted(self):
        """
        The extensions are what make a module's own documentation render.
        """
        html = markdown.markdown(DOCSTRING, extensions=utils.plugin_interface.MARKDOWN_EXTENSIONS)
        self.assertIn("<table>", html, "A pipe table did not become a table.")
        self.assertIn("<th>", html, "The table lost its header cells.")
        self.assertIn('class="language-json"', html,
                      "A tagged fence did not carry its language to the client.")
        self.assertNotIn("|---|", html, "The pipe syntax survived into the output.")

    @unittest.skipIf(markdown is None, "The optional markdown package is not installed.")
    def test_rendering_an_empty_docstring_does_not_raise(self):
        """
        What `get_all_modules` does for a module with no docstring, end to end.
        """
        cls = module_class("collectu_test_bare", None)
        documentation = utils.plugin_interface.module_docstring(cls)
        html = markdown.markdown(documentation,
                                 extensions=utils.plugin_interface.MARKDOWN_EXTENSIONS)
        self.assertEqual("", html, "An empty docstring should render to nothing.")


class TestInstallPluginRequirement(unittest.TestCase):
    """
    Installing a requirement with uv where it is installed, and with pip where it is not or
    where uv fails.

    uv reads neither pip.conf nor PIP_INDEX_URL and brings its own certificates, so a network
    set up for pip alone can fail with uv. The fallback is what keeps such an installation
    installing, which is why it is asserted here.
    """

    UV_BINARY = os.path.join("venv", "bin", "uv")
    """Where the stand-in uv package says its binary is. Nothing runs it: subprocess.run is patched."""

    def setUp(self):
        # Every test here is about a requirement that still has to be installed.
        patcher = mock.patch.object(utils.plugin_interface, "requirement_is_installed",
                                    return_value=(False, "Requirement 'six' is not installed."))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.dict(os.environ, {"AUTO_INSTALL": "1"})
        patcher.start()
        self.addCleanup(patcher.stop)
        # A stand-in for the uv package, so the tests do not depend on it being installed.
        self.uv = types.ModuleType("uv")
        self.uv.find_uv_bin = lambda: self.UV_BINARY
        patcher = mock.patch.dict(sys.modules, {"uv": self.uv})
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def install(*outcomes) -> tuple[int, list[list[str]]]:
        """
        Installs 'six==1.17.0' with subprocess.run answering the given outcomes in turn.

        :returns: The return code, and the commands that were run.
        """
        with mock.patch.object(subprocess, "run", side_effect=outcomes) as run:
            return_code = utils.plugin_interface.install_plugin_requirement("six==1.17.0")
        return return_code, [call.args[0] for call in run.call_args_list]

    def test_uv_comes_first_and_installs_into_the_running_interpreter(self):
        """
        Without --python, uv only installs into an activated venv or a .venv, and the Docker
        image's venv is neither.
        """
        self.assertEqual([("uv", [self.UV_BINARY, "pip", "install", "--python", sys.executable, "six==1.17.0"]),
                          ("pip", [sys.executable, "-m", "pip", "install", "six==1.17.0"])],
                         utils.plugin_interface.installer_commands("six==1.17.0"))

    def test_pip_alone_without_uv(self):
        with mock.patch.dict(sys.modules, {"uv": None}):  # Makes 'import uv' raise ImportError.
            commands = utils.plugin_interface.installer_commands("six==1.17.0")
        self.assertEqual(["pip"], [installer for installer, _ in commands])

    def test_pip_alone_without_the_uv_binary(self):
        def binary_not_found():
            raise FileNotFoundError("Could not find the uv binary.")

        self.uv.find_uv_bin = binary_not_found
        commands = utils.plugin_interface.installer_commands("six==1.17.0")
        self.assertEqual(["pip"], [installer for installer, _ in commands])

    def test_nothing_is_reinstalled_by_force(self):
        """
        The flag reinstalled the whole dependency tree at the newest versions allowed, which
        could move a package requirements.txt pins.
        """
        for installer, command in utils.plugin_interface.installer_commands("six==1.17.0"):
            with self.subTest(installer=installer):
                self.assertNotIn("--force-reinstall", command)
                self.assertNotIn("--reinstall", command)

    def test_what_uv_installed_is_logged(self):
        """
        uv reports on stderr and leaves stdout, where the log used to read from, empty.
        """
        with self.assertLogs(utils.plugin_interface.logger, level="INFO") as logs:
            return_code, commands = self.install(
                subprocess.CompletedProcess([], 0, stdout="", stderr="Installed 1 package in 12ms\n + six==1.17.0\n"))
        self.assertEqual(0, return_code)
        self.assertEqual(1, len(commands), "pip ran although uv succeeded.")
        self.assertIn("+ six==1.17.0", "\n".join(logs.output), "What uv installed is missing from the log.")

    def test_a_failing_uv_falls_back_to_pip(self):
        with self.assertLogs(utils.plugin_interface.logger, level="WARNING") as logs:
            return_code, commands = self.install(
                subprocess.CalledProcessError(2, [], stderr="error: invalid peer certificate: UnknownIssuer"),
                subprocess.CompletedProcess([], 0, stdout="Successfully installed six-1.17.0", stderr=""))
        self.assertEqual(0, return_code)
        self.assertEqual([self.UV_BINARY, sys.executable], [command[0] for command in commands])
        self.assertIn("UnknownIssuer", "\n".join(logs.output), "Why uv failed is missing from the log.")

    def test_a_uv_that_cannot_start_falls_back_to_pip(self):
        with self.assertLogs(utils.plugin_interface.logger, level="WARNING") as logs:
            return_code, commands = self.install(
                OSError(8, "Exec format error"),
                subprocess.CompletedProcess([], 0, stdout="Successfully installed six-1.17.0", stderr=""))
        self.assertEqual(0, return_code)
        self.assertEqual([self.UV_BINARY, sys.executable], [command[0] for command in commands])
        self.assertIn("Exec format error", "\n".join(logs.output), "Why uv failed is missing from the log.")

    def test_the_installation_fails_when_every_installer_does(self):
        with self.assertLogs(utils.plugin_interface.logger, level="WARNING") as logs:
            return_code, _ = self.install(
                subprocess.CalledProcessError(1, [], stderr="error: No solution found"),
                subprocess.CalledProcessError(1, [], stderr="ERROR: No matching distribution found"))
        self.assertEqual(1, return_code)
        output = "\n".join(logs.output)
        self.assertIn("No solution found", output, "uv's error is missing from the log.")
        self.assertIn("No matching distribution found", output, "pip's error is missing from the log.")

    @unittest.skipIf(uv is None, "The uv package is not installed.")
    def test_the_installed_uv_binary_runs(self):
        """
        The real package, not the stand-in: its binary is found and starts on this platform.
        """
        result = subprocess.run([uv.find_uv_bin(), "--version"], capture_output=True, text=True, check=True)
        self.assertTrue(result.stdout.startswith("uv "), "Unexpected version output: {0}".format(result.stdout))


if __name__ == "__main__":
    unittest.main()
