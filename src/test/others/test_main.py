"""
The app as it is started: main.py, run in a copy of the app in a directory of its own, so the settings file and the
logs of the checkout are left alone.
"""
import configparser
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

# Internal imports.
import config

SRC: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
"""The src folder of the checkout."""


def _ignore(directory: str, names: list[str]) -> list[str]:
    """
    What is not copied: the tests, the interface submodule, compiled files and every module but the base classes -
    the modules installed in the checkout are not part of the app.
    """
    ignored = [name for name in names if name in ("test", "interface", "__pycache__") or name.endswith(".pyc")]
    if os.path.normcase(os.path.abspath(directory)) == os.path.normcase(os.path.join(SRC, "modules")):
        ignored += [name for name in names if name not in ("__init__.py", "base")]
    return ignored


class TestMain(unittest.TestCase):
    """
    What the app does before it gets to its command line: setting up the logging, completing the settings file,
    checking its requirements and loading its modules - and the exit code it leaves with.
    """

    @classmethod
    def setUpClass(cls):
        cls._directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.root = os.path.realpath(cls._directory.name)
        shutil.copytree(SRC, os.path.join(cls.root, "src"), ignore=_ignore)
        for folder in ("configuration", "data", "logs"):
            os.makedirs(os.path.join(cls.root, folder))

    @classmethod
    def tearDownClass(cls):
        cls._directory.cleanup()

    def setUp(self):
        with open(os.path.join(self.root, config.SETTINGS_FILENAME), "w", encoding="utf-8") as file:
            file.write("[env]\napp_id =\nlocal_admin_password =\napp_description = smoke-test\n"
                       "auto_install = 0\nreport_to_hub = 0\napi = 0\nmotherships = []\n")

    @staticmethod
    def _settings_names() -> set[str]:
        """The names of the settings, which the environment of the test run may hold as well."""
        parser = configparser.ConfigParser(comment_prefixes="/", allow_no_value=True)
        parser.read(os.path.join(SRC, "..", "settings.ini"), encoding="utf-8")
        names = {name.upper() for name in parser["env"]} if parser.has_section("env") else set()
        return names | {"HUB_USERNAME", "GIT_ACCESS_TOKEN", "HIERARCHY_PATH", "APP_ID", "LOCAL_ADMIN_PASSWORD"}

    def _main(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = {key: value for key, value in os.environ.items() if key not in self._settings_names()}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run([sys.executable, "main.py", *arguments], cwd=os.path.join(self.root, "src"),
                              env=environment, capture_output=True, text=True, timeout=120)

    def test_the_app_starts_and_tells_what_it_is(self):
        result = self._main("--about")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"{config.APP_NAME}\n{config.CONTACT}\n", result.stdout)
        self.assertIn(f"Thank you for using {config.APP_NAME}!", result.stdout)
        with open(os.path.join(self.root, "logs", "Logs.log"), encoding="utf-8") as log:
            self.assertIn("API access token file 'api_access_token.txt' does not exist", log.read(),
                          "Warnings are written to the log file.")

    def test_the_first_start_completes_the_settings_file_without_showing_the_password(self):
        result = self._main("--about")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        parser = configparser.ConfigParser()
        parser.read(os.path.join(self.root, config.SETTINGS_FILENAME), encoding="utf-8")
        settings = parser["env"]
        self.assertEqual(str(uuid.UUID(settings["app_id"])), settings["app_id"])
        password = settings["local_admin_password"]
        self.assertEqual(len(password), 16)
        self.assertNotIn(password, result.stdout + result.stderr)
        with open(os.path.join(self.root, "logs", "Logs.log"), encoding="utf-8") as log:
            self.assertNotIn(password, log.read())

    def test_a_configuration_file_which_does_not_exist_fails_the_start(self):
        result = self._main("--run", "missing.yml")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("'missing.yml' could not be found in the configuration directory", result.stderr)

    def test_an_invalid_command_line_fails_the_start(self):
        result = self._main("--unknown")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("unrecognized arguments: --unknown", result.stderr)


if __name__ == '__main__':
    unittest.main()
