import unittest
import logging
import os
import tempfile

# Internal imports.
import config
import data_layer
import utils.hierarchy
import utils.initialization


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


if __name__ == '__main__':
    unittest.main()
