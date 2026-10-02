"""
Rendering a module's docstring into the payload `GET /modules/` returns, and installing the
third-party requirements of a module.
"""
import importlib
import os
import subprocess
import sys
import types
import unittest
from unittest import mock

# Internal imports.
import data_layer
import modules
import utils.plugin_interface
from test import helpers

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

    def test_a_requirement_which_is_installed_is_not_installed_again(self):
        with mock.patch.object(utils.plugin_interface, "requirement_is_installed", return_value=(True, "")):
            return_code, commands = self.install()
        self.assertEqual((return_code, commands), (0, []))

    def test_nothing_is_installed_without_auto_install(self):
        os.environ["AUTO_INSTALL"] = "0"
        with self.assertLogs(utils.plugin_interface.logger, level="CRITICAL"):
            return_code, commands = self.install()
        self.assertEqual((return_code, commands), (1, []))

    def test_an_unexpected_error_is_reported(self):
        with mock.patch.object(utils.plugin_interface, "installer_commands", side_effect=RuntimeError("Broken.")), \
                self.assertLogs(utils.plugin_interface.logger, level="ERROR"):
            self.assertEqual(utils.plugin_interface.install_plugin_requirement("six==1.17.0"), 1)


class TestRequirementIsInstalled(unittest.TestCase):
    """
    Whether a requirement of a module is met by what is installed, for every kind of specifier pip knows.
    """

    def test_an_installed_requirement_is_satisfied(self):
        import requests
        for requirement in ("requests", f"requests=={requests.__version__}", "requests>=1.0", "requests>=1.0,<999",
                            "requests[socks]>=1.0", "Requests>=1.0"):
            with self.subTest(requirement=requirement):
                satisfied, message = utils.plugin_interface.requirement_is_installed(requirement)
                self.assertTrue(satisfied, message)

    def test_an_installed_requirement_in_another_version_is_not_satisfied(self):
        satisfied, message = utils.plugin_interface.requirement_is_installed("requests<1.0")
        self.assertFalse(satisfied)
        self.assertIn("is not satisfied", message)

    def test_a_requirement_which_is_not_installed_is_not_satisfied(self):
        satisfied, message = utils.plugin_interface.requirement_is_installed("collectu-test-not-installed==1.0")
        self.assertEqual((satisfied, message), (False, "Requirement 'collectu-test-not-installed' is not installed."))

    def test_a_malformed_requirement_is_not_satisfied(self):
        self.assertEqual(utils.plugin_interface.requirement_is_installed("requests>=>1"),
                         (False, "Malformed requirement string 'requests>=>1'."))

    def test_without_packaging_nothing_is_satisfied(self):
        with mock.patch.object(utils.plugin_interface, "Requirement", None):
            satisfied, message = utils.plugin_interface.requirement_is_installed("requests")
        self.assertFalse(satisfied)
        self.assertIn("'packaging' library is not installed", message)


class TestModuleRegistry(helpers.GlobalStateTestCase):
    """
    The classes a module file provides are registered by the name a configuration uses for them.
    """

    def test_an_input_file_provides_up_to_three_modules(self):
        module = types.SimpleNamespace(InputModule="input", VariableModule="variable", TagModule="tag")
        self.assertEqual(utils.plugin_interface.module_registry_entries("inputs.opc_ua.client_1", module),
                         [("inputs.opc_ua.client_1", "input"),
                          ("inputs.opc_ua.client_1.variable", "variable"),
                          ("inputs.opc_ua.client_1.tag", "tag")])

    def test_only_the_classes_a_file_has_are_registered(self):
        module = types.SimpleNamespace(VariableModule="variable", OutputModule="output")
        self.assertEqual(utils.plugin_interface.module_registry_entries("inputs.general.random_1", module),
                         [("inputs.general.random_1.variable", "variable")])

    def test_output_and_processor_files_provide_one_module(self):
        module = types.SimpleNamespace(OutputModule="output", ProcessorModule="processor")
        self.assertEqual(utils.plugin_interface.module_registry_entries("outputs.general.logger_1", module),
                         [("outputs.general.logger_1", "output")])
        self.assertEqual(utils.plugin_interface.module_registry_entries("processors.general.filter_1", module),
                         [("processors.general.filter_1", "processor")])

    def test_files_of_another_kind_provide_nothing(self):
        module = types.SimpleNamespace(OutputModule="output")
        self.assertEqual(utils.plugin_interface.module_registry_entries("base.base", module), [])
        self.assertFalse(utils.plugin_interface.register_module("base.base", module))
        self.assertEqual(data_layer.registered_modules, {})

    def test_the_entries_are_registered(self):
        self.assertTrue(utils.plugin_interface.register_module("outputs.general.logger_1",
                                                               types.SimpleNamespace(OutputModule="output")))
        self.assertEqual(data_layer.registered_modules, {"outputs.general.logger_1": "output"})


class TestModuleDescriptions(helpers.GlobalStateTestCase):
    """
    What the editor learns about the installed modules: their parameters, their requirements and whether they can be
    installed here.
    """

    def setUp(self):
        super().setUp()
        data_layer.registered_modules.update(helpers.MODULES)

    @staticmethod
    def _describe(name: str, **filters) -> dict:
        return next(module for module in utils.plugin_interface.get_all_modules(**filters)
                    if module["module_name"] == name)

    def test_every_module_is_described_with_its_type(self):
        types_by_name = {module["module_name"]: module["module_type"]
                         for module in utils.plugin_interface.get_all_modules()}
        self.assertEqual(types_by_name, {"inputs.test.client_1": "input", "inputs.test.client_1.variable": "input",
                                         "inputs.test.client_1.tag": "input", "inputs.test.source_1.variable": "input",
                                         "processors.test.multiplier_1": "processor",
                                         "outputs.test.collector_1": "output", "outputs.test.buffer_1": "output"})

    def test_the_modules_are_filtered_by_type(self):
        for flag, prefix in (("inputs", "inputs."), ("outputs", "outputs."), ("processors", "processors.")):
            with self.subTest(filter=flag):
                names = [module["module_name"] for module in utils.plugin_interface.get_all_modules(**{flag: True})]
                self.assertTrue(names)
                self.assertTrue(all(name.startswith(prefix) for name in names), names)

    def test_the_parameters_are_described(self):
        parameters = {parameter["key"]: parameter
                      for parameter in self._describe("processors.test.multiplier_1")["parameters"]}
        self.assertEqual(parameters["factor"], {"key": "factor", "data_type": "int", "required": False,
                                                "category": "basic", "description": "The factor.", "secret": False,
                                                "default": 2, "dynamic": True})
        self.assertEqual((parameters["links"]["data_type"], parameters["links"]["default"],
                          parameters["links"]["category"]), ("list[str]", [], "general"))
        self.assertTrue(parameters["module_name"]["required"])

    def test_what_is_particular_to_a_module_type_is_described(self):
        self.assertTrue(self._describe("outputs.test.buffer_1")["can_be_buffer"])
        self.assertFalse(self._describe("outputs.test.collector_1")["can_be_buffer"])
        processor = self._describe("processors.test.multiplier_1")
        self.assertEqual((processor["field_requirements"], processor["tag_requirements"]),
                         (["(key value with number)"], []))
        self.assertNotIn("can_be_buffer", processor)

    def test_the_documentation_is_rendered(self):
        description = self._describe("outputs.test.collector_1")
        self.assertEqual(description["documentation"], helpers.__doc__)
        if markdown is not None:
            self.assertIn("<p>", description["documentation_html"])

    def test_a_module_of_an_unknown_type_is_left_out(self):
        data_layer.registered_modules["helpers.test_1"] = helpers.Collector
        with self.assertLogs(utils.plugin_interface.logger, level="ERROR"):
            names = [module["module_name"] for module in utils.plugin_interface.get_all_modules()]
        self.assertNotIn("helpers.test_1", names)

    def test_the_requirement_status_says_whether_a_module_can_be_imported(self):
        class Missing(helpers.Collector):
            third_party_requirements = ["collectu-test-missing==1.0", "requests"]

            @classmethod
            def import_third_party_requirements(cls) -> bool:
                raise ImportError("No module named 'collectu_test_missing'")

        data_layer.registered_modules = {"outputs.test.collector_1": helpers.Collector,
                                         "outputs.test.missing_1": Missing}

        self.assertEqual(utils.plugin_interface.get_plugin_requirement_status(),
                         [{"name": "outputs.test.collector_1", "description": "An output of the tests.",
                           "requirements": [], "installed": True},
                          {"name": "outputs.test.missing_1", "description": "An output of the tests.",
                           "requirements": ["collectu-test-missing==1.0", "requests"], "installed": False}])
        self.assertEqual(utils.plugin_interface.get_list_of_all_module_requirements(),
                         ["collectu-test-missing==1.0", "requests"])

    def test_the_requirements_of_all_modules_are_listed_once_and_sorted(self):
        data_layer.registered_modules = {
            "outputs.a_1": types.SimpleNamespace(third_party_requirements=["b==1", "A>=2"]),
            "outputs.b_1": types.SimpleNamespace(third_party_requirements=["b==1", "a"])}
        self.assertEqual(utils.plugin_interface.get_list_of_all_module_requirements(), ["a", "A>=2", "b==1"])


OUTPUT_MODULE = '''"""
An output module of the tests.
"""
from modules.base.outputs.base import AbstractOutputModule


class OutputModule(AbstractOutputModule):
    description = "{description}"

    def _run(self, data):
        pass
'''
"""The code of a module file, as it is downloaded from the hub."""

INPUT_MODULE = '''"""
An input module of the tests, with its variable and tag module.
"""
from modules.base.inputs.base import AbstractInputModule, AbstractTagModule, AbstractVariableModule


class InputModule(AbstractInputModule):
    pass


class VariableModule(AbstractVariableModule):
    pass


class TagModule(AbstractTagModule):
    def _run(self):
        return {}
'''


class _ModuleFolderTestCase(helpers.GlobalStateTestCase):
    """
    Runs each test with a module folder of its own: src/modules of a directory laid out like a checkout, whose
    packages are found as the modules package's, in place of the checkout's. What the test imports is forgotten
    afterwards.
    """

    def setUp(self):
        super().setUp()
        self.root = self.enter_app_directory()
        self.folder = os.path.join(self.root, "src", "modules")
        os.makedirs(self.folder)

        patcher = mock.patch.dict(sys.modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in list(sys.modules):
            if name.startswith(("modules.inputs", "modules.outputs", "modules.processors", "modules.custom")):
                del sys.modules[name]

        saved_path, saved_modules_path = list(sys.path), list(modules.__path__)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), saved_path))
        self.addCleanup(lambda: modules.__path__.__setitem__(slice(None), saved_modules_path))
        # The test's folder alone: the checkout's own module folder holds whatever modules are installed there (it is
        # git-ignored), which would be loaded and listed along with the ones of the test. The base classes the test
        # modules subclass stay importable, as helpers imported them already and they are found in sys.modules.
        modules.__path__[:] = [self.folder]
        os.environ.pop("CUSTOM_MODULE_FOLDER", None)

    def write(self, path: str, code: str) -> str:
        """
        Write a module file and the __init__.py of each package on the way to it.

        :param path: The path below the module folder.
        :param code: The code.
        :returns: The path of the file.
        """
        file = os.path.join(self.folder, path)
        directory = os.path.dirname(file)
        while directory != self.folder:
            os.makedirs(directory, exist_ok=True)
            open(os.path.join(directory, "__init__.py"), "a").close()
            directory = os.path.dirname(directory)
        with open(file, "w", encoding="utf-8") as handle:
            handle.write(code)
        importlib.invalidate_caches()
        return file


class TestLoadModules(_ModuleFolderTestCase):
    """
    The modules of the custom module folder are loaded after the others, and win over them.
    """

    def setUp(self):
        super().setUp()
        os.environ["CUSTOM_MODULE_FOLDER"] = "custom"
        self.write("custom/outputs/test/collector_1.py", OUTPUT_MODULE.format(description="Custom."))

    def test_the_modules_of_the_custom_module_folder_are_registered(self):
        utils.plugin_interface.load_modules()
        self.assertEqual(data_layer.registered_modules["outputs.test.collector_1"].description, "Custom.")

    def test_an_input_file_registers_its_variable_and_tag_modules(self):
        self.write("custom/inputs/test/client_1.py", INPUT_MODULE)
        utils.plugin_interface.load_modules()
        self.assertEqual(sorted(name for name in data_layer.registered_modules if name.startswith("inputs.")),
                         ["inputs.test.client_1", "inputs.test.client_1.tag", "inputs.test.client_1.variable"])

    def test_a_custom_module_wins_over_one_of_the_same_name(self):
        data_layer.registered_modules["outputs.test.collector_1"] = helpers.Collector
        with self.assertLogs(utils.plugin_interface.logger, level="WARNING") as logs:
            utils.plugin_interface.load_modules()
        self.assertEqual(data_layer.registered_modules["outputs.test.collector_1"].description, "Custom.")
        self.assertIn("is now overwritten with the one in your custom module folder", "\n".join(logs.output))

    def test_a_module_which_can_not_be_imported_does_not_stop_the_others(self):
        self.write("custom/outputs/test/broken_1.py", "def broken(:\n")
        with self.assertLogs(utils.plugin_interface.logger, level="WARNING") as logs:
            utils.plugin_interface.load_modules()
        self.assertIn("outputs.test.collector_1", data_layer.registered_modules)
        self.assertNotIn("outputs.test.broken_1", data_layer.registered_modules)
        self.assertIn("broken_1", "\n".join(logs.output))

    def test_without_a_custom_module_folder_none_is_loaded(self):
        os.environ.pop("CUSTOM_MODULE_FOLDER")
        self.assertIsNone(utils.plugin_interface.get_custom_module_folder())
        utils.plugin_interface.load_modules()
        self.assertNotIn("outputs.test.collector_1", data_layer.registered_modules)

    def test_a_custom_module_folder_which_does_not_exist_is_ignored(self):
        os.environ["CUSTOM_MODULE_FOLDER"] = "missing"
        self.assertIsNone(utils.plugin_interface.get_custom_module_folder())


class TestModuleFiles(_ModuleFolderTestCase):
    """
    Writing a module file, as it is downloaded from the hub, and listing the module files there are.
    """

    def test_a_module_is_written_imported_and_registered(self):
        code = OUTPUT_MODULE.format(description="Downloaded.")
        utils.plugin_interface.write_module_to_file(module_name="outputs.test.collector_1", code=code)

        with open(os.path.join(self.folder, "outputs", "test", "collector_1.py"), encoding="utf-8") as file:
            self.assertEqual(file.read(), code)
        for package in ("outputs", os.path.join("outputs", "test")):
            self.assertTrue(os.path.isfile(os.path.join(self.folder, package, "__init__.py")), package)
        self.assertEqual(data_layer.registered_modules["outputs.test.collector_1"].description, "Downloaded.")

    def test_a_new_version_replaces_the_one_imported_before(self):
        for description in ("First.", "Second."):
            with self.assertLogs(utils.plugin_interface.logger, level="INFO"):
                utils.plugin_interface.write_module_to_file(module_name="outputs.test.collector_1",
                                                            code=OUTPUT_MODULE.format(description=description))
        self.assertEqual(data_layer.registered_modules["outputs.test.collector_1"].description, "Second.")

    def test_a_file_is_only_written_if_asked(self):
        utils.plugin_interface.write_module_to_file(module_name="outputs.test.collector_1", code="# Code.\n",
                                                    import_module=False)
        self.assertTrue(os.path.isfile(os.path.join(self.folder, "outputs", "test", "collector_1.py")))
        self.assertEqual(data_layer.registered_modules, {})

    def test_a_module_of_an_unknown_type_is_not_written(self):
        with self.assertRaises(Exception):
            utils.plugin_interface.write_module_to_file(module_name="helpers.test_1", code="# Code.\n")
        self.assertEqual(os.listdir(self.folder), [])

    def test_a_module_of_the_custom_module_folder_is_updated_there(self):
        os.environ["CUSTOM_MODULE_FOLDER"] = "custom"
        custom = self.write("custom/outputs/test/collector_1.py", "# Old code.\n")

        utils.plugin_interface.write_module_to_file(module_name="outputs.test.collector_1", code="# New code.\n",
                                                    import_module=False)

        with open(custom, encoding="utf-8") as file:
            self.assertEqual(file.read(), "# New code.\n")
        self.assertFalse(os.path.exists(os.path.join(self.folder, "outputs")))

    def test_the_module_files_are_listed_by_module_name(self):
        os.environ["CUSTOM_MODULE_FOLDER"] = "custom"
        self.write("outputs/test/collector_1.py", "# An output.\n")
        self.write("custom/processors/test/multiplier_1.py", "# A processor.\n")
        self.write("custom/helpers.py", "# No module.\n")

        files = utils.plugin_interface.get_all_module_files()
        self.assertEqual(list(files), ["outputs.test.collector_1"])
        self.assertEqual(files["outputs.test.collector_1"]["code"], "# An output.\n")

        custom_files = utils.plugin_interface.get_all_custom_module_files()
        self.assertEqual(list(custom_files), ["processors.test.multiplier_1"])
        self.assertEqual(custom_files["processors.test.multiplier_1"]["code"], "# A processor.\n")

    def test_without_a_custom_module_folder_there_are_no_custom_module_files(self):
        os.environ.pop("CUSTOM_MODULE_FOLDER", None)
        self.assertEqual(utils.plugin_interface.get_all_custom_module_files(), {})


if __name__ == "__main__":
    unittest.main()
