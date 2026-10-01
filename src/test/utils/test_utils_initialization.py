import unittest
import base64
import configparser
import logging
import os
import socket
import stat
import tempfile
import types
import uuid
from unittest import mock

# Internal imports.
import config
import data_layer
import utils.hierarchy
import utils.initialization
import utils.plugin_interface
import utils.resilient_session
from test.helpers import GlobalStateTestCase

# Third party imports.
import requests


class TestSettingsFileEncoding(unittest.TestCase):
    """
    Reading the settings file as what it is rather than as whatever the machine prefers.

    `open()` without an encoding uses the locale encoding. That is UTF-8 on the Linux hosts
    and containers this runs on, and cp1252 on a Windows one - so this passes either way on
    CI and only ever broke on a developer's machine, which is exactly why it is asserted
    here rather than left to be noticed.

    The symptom was a site called 'Goethestraße' arriving at the hub as 'GoethestraÃŸe',
    under which name it was then shown in the fleet list and written back into the file.
    """

    NON_ASCII = {"site": "Goethestraße",
                 "area": "Büro",
                 "app_description": "Prüfstand Nr. 3"}
    """Values that are one byte in cp1252 and two in UTF-8, which is where the two disagree."""

    def setUp(self):
        # The function reads '../<SETTINGS_FILENAME>' relative to the working directory, so
        # it gets a directory of its own rather than the checkout's real settings file.
        self._directory = tempfile.TemporaryDirectory()
        self._previous_cwd = os.getcwd()
        self._previous_environ = dict(os.environ)
        self._previous_settings = dict(data_layer.settings)

        root = self._directory.name
        os.makedirs(os.path.join(root, "src"))
        with open(os.path.join(root, config.SETTINGS_FILENAME), "w", encoding="utf-8") as handle:
            handle.write("[env]\n")
            handle.write("app_id = 11111111-1111-1111-1111-111111111111\n")
            handle.write("local_admin_password = irrelevant\n")
            for key, value in self.NON_ASCII.items():
                handle.write(f"{key} = {value}\n")
        os.chdir(os.path.join(root, "src"))

        for key in list(self.NON_ASCII) + ["HUB_API_ACCESS_TOKEN", "REPORT_TO_HUB", "HUB_USERNAME"]:
            os.environ.pop(key.upper(), None)
        data_layer.settings.clear()

    def tearDown(self):
        os.chdir(self._previous_cwd)
        os.environ.clear()
        os.environ.update(self._previous_environ)
        data_layer.settings.clear()
        data_layer.settings.update(self._previous_settings)
        self._directory.cleanup()

    def test_the_settings_file_is_processed_without_an_error(self):
        """
        It reports its own failures into the log and answers False, so a test that only
        checked the values it happened to set before giving up would pass over a function
        that aborted half way through.
        """
        with self.assertLogs(level="ERROR") as captured:
            logging.getLogger().error("placeholder, so assertLogs has something to catch")
            utils.initialization.load_and_process_settings_file()

        self.assertEqual([record for record in captured.records
                          if "Could not initialize application" in record.getMessage()], [])

    def test_a_umlaut_survives_being_read_from_the_settings_file(self):
        utils.initialization.load_and_process_settings_file()

        for key, value in self.NON_ASCII.items():
            with self.subTest(setting=key):
                self.assertEqual(os.environ.get(key.upper()), value)

    def test_a_umlaut_survives_being_written_back(self):
        """
        The settings are written again whenever one is changed through the api. Read with one
        encoding and written with another, the file degrades a little on every save.
        """
        utils.initialization.load_and_process_settings_file()
        utils.initialization.update_env_variables()

        os.environ.clear()
        os.environ.update({k: v for k, v in self._previous_environ.items()
                           if k.upper() not in {key.upper() for key in self.NON_ASCII}})
        utils.initialization.load_and_process_settings_file()

        for key, value in self.NON_ASCII.items():
            with self.subTest(setting=key):
                self.assertEqual(os.environ.get(key.upper()), value)

    def test_the_hierarchy_is_built_from_the_decoded_values(self):
        """
        What the app reports to the hub and publishes under. A wrongly decoded level reaches
        every one of those, so the path is the place the damage would actually be seen.
        """
        os.environ["ENTERPRISE"] = "acme"

        utils.initialization.load_and_process_settings_file()

        self.assertEqual(utils.hierarchy.path(), "acme/Goethestraße/Büro/Prüfstand Nr. 3")


class _Session:
    """
    Stands in for the session asking the hub whom the api access token belongs to.
    """

    def __init__(self, answer):
        self.headers = {}
        self._answer = answer

    def get(self, url: str, timeout=None):
        if isinstance(self._answer, Exception):
            raise self._answer
        return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: self._answer)


class TestSettingsFile(GlobalStateTestCase):
    """
    load_and_process_settings_file: the settings file fills the environment, unless a variable is set already, and
    what is missing on the first start is generated and written back.
    """

    VARIABLES = ("APP_ID", "LOCAL_ADMIN_PASSWORD", "APP_DESCRIPTION", "API_PORT", "HUB_API_ACCESS_TOKEN",
                 "HUB_USERNAME", "REPORT_TO_HUB", "GIT_ACCESS_TOKEN", "ENTERPRISE", "HIERARCHY_PATH", "SITE", "AREA",
                 "WORK_CENTER", "WORK_UNIT", "EQUIPMENT_MODULE")
    """The variables the tests below read. Unset, so the environment running the tests does not leak into them."""

    def setUp(self):
        super().setUp()
        self.root = self.enter_app_directory()
        for variable in self.VARIABLES:
            os.environ.pop(variable, None)

    def _write_settings(self, **values: str):
        values = {"app_id": "11111111-1111-1111-1111-111111111111", "local_admin_password": "secret",
                  "app_description": "press-3", **values}
        with open(os.path.join(self.root, config.SETTINGS_FILENAME), "w", encoding="utf-8") as file:
            file.write("[env]\n" + "".join(f"{key} = {value}\n" for key, value in values.items()))

    def _read_settings(self) -> dict[str, str]:
        parser = configparser.ConfigParser()
        parser.read(os.path.join(self.root, config.SETTINGS_FILENAME), encoding="utf-8")
        return dict(parser.items("env"))

    def _write_file(self, filename: str, content: str):
        with open(os.path.join(self.root, filename), "w", encoding="utf-8") as file:
            file.write(content)

    def test_the_settings_become_environment_variables(self):
        self._write_settings(api_port="8181")

        self.assertFalse(utils.initialization.load_and_process_settings_file(), "Nothing had to be written back.")

        self.assertEqual((os.environ["API_PORT"], os.environ["APP_DESCRIPTION"]), ("8181", "press-3"))
        self.assertEqual(data_layer.settings["API_PORT"], "8181")

    def test_an_environment_variable_wins_over_the_settings_file(self):
        """
        That is how a container is configured.
        """
        self._write_settings(api_port="8181")
        os.environ["API_PORT"] = "9000"

        utils.initialization.load_and_process_settings_file()

        self.assertEqual((os.environ["API_PORT"], data_layer.settings["API_PORT"]), ("9000", "9000"))
        self.assertEqual(self._read_settings()["api_port"], "8181")

    def test_a_missing_app_id_is_generated_and_written_back(self):
        self._write_settings(app_id="")

        self.assertTrue(utils.initialization.load_and_process_settings_file())

        app_id = os.environ["APP_ID"]
        self.assertEqual(str(uuid.UUID(app_id)), app_id)
        self.assertEqual(self._read_settings()["app_id"], app_id)
        self.assertEqual(data_layer.settings["APP_ID"], app_id)

    def test_a_missing_password_is_generated_and_written_back_but_never_logged(self):
        """
        Logs are mirrored into the reports sent to the hub and to every mothership.
        """
        self._write_settings(local_admin_password="")

        with self.assertLogs(level="DEBUG") as logs:
            self.assertTrue(utils.initialization.load_and_process_settings_file())

        password = os.environ["LOCAL_ADMIN_PASSWORD"]
        self.assertEqual(len(password), 16)
        self.assertEqual(self._read_settings()["local_admin_password"], password)
        self.assertNotIn(password, "\n".join(logs.output))

    def test_a_missing_app_description_is_the_hostname(self):
        self._write_settings(app_description="")
        self.assertTrue(utils.initialization.load_and_process_settings_file())
        self.assertEqual(os.environ["APP_DESCRIPTION"], socket.gethostname())

    def test_an_empty_hub_token_is_not_set(self):
        """
        It would show up empty in the settings of the user interface and overwrite the real one when they are saved.
        """
        self._write_settings(hub_api_access_token="")
        utils.initialization.load_and_process_settings_file()
        self.assertNotIn("HUB_API_ACCESS_TOKEN", os.environ)
        self.assertNotIn("HUB_API_ACCESS_TOKEN", data_layer.settings)

    def test_the_api_access_token_is_read_from_its_file(self):
        self._write_settings()
        self._write_file("api_access_token.txt", "the-file-token\n")
        os.environ["HUB_API_ACCESS_TOKEN"] = "the-environment-token"

        with self.assertLogs(utils.initialization.logger, level="WARNING"):
            utils.initialization.load_and_process_settings_file()

        self.assertEqual(os.environ["HUB_API_ACCESS_TOKEN"], "the-file-token")

    def test_the_hub_username_is_asked_for_with_the_token(self):
        self._write_settings(report_to_hub="1")
        os.environ["HUB_API_ACCESS_TOKEN"] = "the-apps-own-token"
        session = _Session({"username": "acme"})

        with mock.patch.object(utils.resilient_session, "create_resilient_session", return_value=session):
            utils.initialization.load_and_process_settings_file()

        self.assertEqual(session.headers, {"Authorization": "Bearer the-apps-own-token"})
        self.assertEqual(os.environ["HUB_USERNAME"], "acme")
        self.assertEqual(os.environ["HIERARCHY_PATH"], "acme/press-3", "The enterprise is known from now on.")

    def test_an_invalid_token_is_reported_and_the_rest_goes_on(self):
        self._write_settings(report_to_hub="1", api_port="8181")
        os.environ["HUB_API_ACCESS_TOKEN"] = "an-invalid-token"

        with mock.patch.object(utils.resilient_session, "create_resilient_session",
                               return_value=_Session(requests.HTTPError("401 Error"))), \
                self.assertLogs(utils.initialization.logger, level="ERROR") as logs:
            utils.initialization.load_and_process_settings_file()

        self.assertIn("invalid api access token", logs.output[0])
        self.assertNotIn("HUB_USERNAME", os.environ)
        self.assertEqual(os.environ["API_PORT"], "8181")

    def test_the_git_access_token_is_stored_as_a_key_file(self):
        key = "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----\n"
        os.environ["GIT_ACCESS_TOKEN"] = base64.b64encode(key.encode("utf-8")).decode("utf-8")
        self._write_settings()

        utils.initialization.load_and_process_settings_file()

        path = os.path.join(self.root, "git_access_token.txt")
        with open(path, encoding="utf-8") as file:
            self.assertEqual(file.read(), key)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600, "ssh refuses a key others can read.")

    def test_a_malformed_git_access_token_does_not_stop_the_initialization(self):
        os.environ["GIT_ACCESS_TOKEN"] = base64.b64encode(b"\xff\xfe").decode("utf-8")
        self._write_settings()
        self._write_file("api_access_token.txt", "the-file-token\n")

        with self.assertLogs(utils.initialization.logger, level="ERROR") as logs:
            utils.initialization.load_and_process_settings_file()

        self.assertIn("Could not store the GIT_ACCESS_TOKEN", logs.output[0])
        self.assertEqual(os.environ["HUB_API_ACCESS_TOKEN"], "the-file-token")
        self.assertFalse(os.path.exists(os.path.join(self.root, "git_access_token.txt")))

    def test_a_missing_settings_file_is_reported(self):
        with self.assertLogs(utils.initialization.logger, level="ERROR") as logs:
            self.assertFalse(utils.initialization.load_and_process_settings_file())
        self.assertIn("Could not initialize application", logs.output[0])

    def test_changed_settings_are_written_back(self):
        self._write_settings(api_port="8181", site="")
        os.environ["ENTERPRISE"] = "acme"
        utils.initialization.load_and_process_settings_file()
        data_layer.settings.update({"API_PORT": "9001", "SITE": "Stuttgart"})

        utils.initialization.update_env_variables()

        self.assertEqual((os.environ["API_PORT"], self._read_settings()["api_port"]), ("9001", "9001"))
        self.assertEqual(os.environ["HIERARCHY_PATH"], "acme/Stuttgart/press-3")

    def test_settings_which_can_not_be_written_back_are_reported(self):
        with self.assertLogs(utils.initialization.logger, level="ERROR"):
            utils.initialization.update_env_variables()


class TestInstalledAppPackages(GlobalStateTestCase):
    """
    The packages in requirements.txt are installed in exactly the pinned version, or installed if AUTO_INSTALL allows.
    """

    def setUp(self):
        super().setUp()
        self.root = self.enter_app_directory()
        os.environ.pop("MCP", None)
        self.installed: dict[str, str] = {"requests": "2.34.2", "PyYAML": "6.0.3", "ruamel-yaml": "0.18.0"}
        distributions = lambda: [types.SimpleNamespace(metadata={"Name": name}, version=version)
                                 for name, version in self.installed.items()]
        for target, attribute, replacement in ((utils.initialization.importlib.metadata, "distributions",
                                                distributions),
                                               (utils.plugin_interface, "install_plugin_requirement", mock.DEFAULT)):
            patcher = mock.patch.object(target, attribute, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.install = utils.plugin_interface.install_plugin_requirement

    def _requirements(self, content: str, path: str = "requirements.txt"):
        path = os.path.join(self.root, "src", path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)

    def test_matching_packages_are_left_alone(self):
        self._requirements("requests==2.34.2\npyyaml==6.0.3\nruamel.yaml==0.18.0\n")
        with self.assertNoLogs(utils.initialization.logger, level="ERROR"):
            utils.initialization.check_installed_app_packages()
        self.install.assert_not_called()

    def test_comments_and_packages_without_a_pinned_version_are_ignored(self):
        self._requirements("# The packages.\nrequests>=1.0\ntinydb  # Not pinned.\nPyYAML==6.0.3  # Pinned.\n")
        with self.assertNoLogs(utils.initialization.logger, level="ERROR"):
            utils.initialization.check_installed_app_packages()

    def test_a_missing_package_is_installed_with_auto_install(self):
        os.environ["AUTO_INSTALL"] = "1"
        self._requirements("tinydb==4.9.0\n")
        with self.assertLogs(utils.initialization.logger, level="ERROR"):
            utils.initialization.check_installed_app_packages()
        self.install.assert_called_once_with(package="tinydb==4.9.0")

    def test_a_missing_package_is_reported_without_auto_install(self):
        os.environ["AUTO_INSTALL"] = "0"
        self._requirements("tinydb==4.9.0\n")
        with self.assertLogs(utils.initialization.logger, level="CRITICAL"):
            utils.initialization.check_installed_app_packages()
        self.install.assert_not_called()

    def test_another_version_is_replaced_with_auto_install(self):
        os.environ["AUTO_INSTALL"] = "1"
        self._requirements("requests==2.31.0\n")
        with self.assertLogs(utils.initialization.logger, level="ERROR") as logs:
            utils.initialization.check_installed_app_packages()
        self.assertIn("Package version 2.34.2 differs from the one defined in requirements.txt: requests==2.31.0.",
                      logs.output[0])
        self.install.assert_called_once_with(package="requests==2.31.0")

    def test_another_version_is_reported_without_auto_install(self):
        os.environ["AUTO_INSTALL"] = "0"
        self._requirements("requests==2.31.0\n")
        with self.assertLogs(utils.initialization.logger, level="CRITICAL"):
            utils.initialization.check_installed_app_packages()
        self.install.assert_not_called()

    def test_the_requirements_of_the_interface_are_checked_as_well(self):
        os.environ["AUTO_INSTALL"] = "1"
        os.environ["MCP"] = "1"
        self._requirements("requests==2.34.2\n")
        self._requirements("fastapi==0.120.0\nrequests==2.0.0\n", path="interface/requirements.txt")
        self._requirements("mcp==1.20.0\n", path="interface/requirements-mcp.txt")

        with self.assertLogs(utils.initialization.logger, level="ERROR"):
            utils.initialization.check_installed_app_packages()

        self.assertEqual(sorted(call.kwargs["package"] for call in self.install.call_args_list),
                         ["fastapi==0.120.0", "mcp==1.20.0"],
                         "The version requirements.txt pins wins over the one of the interface.")

    def test_package_names_are_compared_as_pip_does(self):
        for written in ("ruamel.yaml", "Ruamel_YAML", "ruamel-yaml"):
            self.assertEqual(utils.initialization._normalize_package_name(written), "ruamel-yaml")


if __name__ == '__main__':
    unittest.main()
