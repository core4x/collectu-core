"""
Reading, validating and writing configurations: Configuration.validate_configuration_from_stream, the methods loading
and saving configurations, and the one directory they are confined to.
"""
import json
import os
import pathlib
import unittest
from unittest import mock

# Internal imports.
import config
import data_layer
import utils.hub_connection
from configuration import Configuration, configuration_path
from test.helpers import AppTestCase, Collector, Source, instance, module_config, wait_for

# Third party imports.
import yaml

PIPELINE: list[dict] = [module_config("source", "inputs.test.source_1.variable", links=["collector"]),
                        module_config("collector", "outputs.test.collector_1")]
"""A source linked to an output, as the editor writes it: without the parameters left at their defaults."""


class TestConfigurationPath(AppTestCase):
    """
    Configuration files are read from and written to the configuration directory, and nowhere else - the filename
    comes from api requests and from tasks of a mothership.
    """

    def _inside(self, *parts: str) -> pathlib.Path:
        return pathlib.Path(self.root, "configuration", *parts)

    def test_a_filename_resolves_inside_the_configuration_directory(self):
        self.assertEqual(configuration_path("press.yml"), self._inside("press.yml"))

    def test_a_subdirectory_is_allowed(self):
        self.assertEqual(configuration_path("line_3/press.yml"), self._inside("line_3", "press.yml"))
        self.assertEqual(configuration_path("line_3/../press.yml"), self._inside("press.yml"))

    def test_a_path_leaving_the_directory_is_refused(self):
        for filename in ("../settings.ini", "line_3/../../settings.ini", os.path.join(self.root, "settings.ini")):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    configuration_path(filename)

    def test_the_directory_itself_is_not_a_file(self):
        for filename in ("", ".", "line_3/.."):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    configuration_path(filename)

    def test_a_link_leading_out_of_the_directory_is_refused(self):
        try:
            os.symlink(os.path.join(self.root, "data"), self._inside("link"), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links can not be created here.")
        with self.assertRaises(ValueError):
            configuration_path("link/stolen.yml")


class TestValidateConfiguration(AppTestCase):
    """
    Configuration.validate_configuration_from_stream: what a configuration has to be to be started.
    """

    @staticmethod
    def _validate(content) -> tuple[list, list, dict]:
        if not isinstance(content, str):
            content = json.dumps(content)
        return Configuration.validate_configuration_from_stream(content)

    def test_modules_are_deserialized_with_their_defaults(self):
        configuration, configuration_dict, errors = self._validate(PIPELINE)

        self.assertEqual(errors, {})
        self.assertEqual([type(module) for module in configuration], [Source.Configuration, Collector.Configuration])
        source = configuration[0]
        self.assertEqual(source.links, ["collector"])
        self.assertEqual(source.worker_count_per_link, 1, "A parameter not given takes its default.")
        self.assertEqual(source.measurement, "test")
        self.assertEqual(configuration_dict, PIPELINE, "The configuration is kept as written, without the defaults.")

    def test_yaml_is_read(self):
        content = ("- id: source\n"
                   "  module_name: inputs.test.source_1.variable\n"
                   "  version: 1\n"
                   "  measurement: pressure\n"
                   "  links:\n"
                   "    - collector\n"
                   "- id: collector\n"
                   "  module_name: outputs.test.collector_1\n"
                   "  version: 1\n")
        configuration, _, errors = self._validate(content)
        self.assertEqual(errors, {})
        self.assertEqual(configuration[0].measurement, "pressure")
        self.assertEqual(configuration[0].links, ["collector"])

    def test_an_empty_configuration_is_valid(self):
        for content in ("", "[]", "null"):
            with self.subTest(content=content):
                self.assertEqual(self._validate(content), ([], [], {}))

    def test_content_which_is_neither_yaml_nor_json_is_reported(self):
        configuration, configuration_dict, errors = self._validate("[{'id': ")
        self.assertEqual((configuration, configuration_dict), ([], []))
        self.assertEqual(list(errors), ["-"])
        self.assertIn("Failed to validate configuration", errors["-"][0])

    def test_an_unknown_module_is_reported_and_left_out(self):
        content = PIPELINE + [{"id": "unknown", "module_name": "outputs.test.unknown_1", "version": 1}]
        with self.assertLogs("collectu.configuration", level="ERROR"):
            configuration, _, errors = self._validate(content)
        self.assertEqual(list(errors), ["unknown"])
        self.assertIn("Unknown module_name 'outputs.test.unknown_1'", errors["unknown"][0])
        self.assertEqual([module.id for module in configuration], ["source", "collector"])

    def test_a_version_this_app_does_not_have_is_reported(self):
        content = [dict(PIPELINE[0]), dict(PIPELINE[1], version=2)]
        with self.assertLogs("collectu.configuration", level="ERROR"):
            _, _, errors = self._validate(content)
        self.assertIn("version '2'", errors["collector"][0])

    def test_a_module_linking_to_an_invalid_one_is_reported_as_well(self):
        """
        The invalid module is left out, so a link to it leads nowhere.
        """
        configuration, _, errors = self._validate([PIPELINE[0], dict(PIPELINE[1], panel="panel-9")])
        self.assertEqual(errors["source"], ["A linked module with the id 'collector' does not exist."])
        self.assertEqual(configuration, [])

    def test_a_missing_module_is_downloaded_from_the_hub_if_that_is_allowed(self):
        os.environ["AUTO_DOWNLOAD"] = "1"
        collector = data_layer.registered_modules.pop("outputs.test.collector_1")

        def download(module_name: str, version: int) -> bool:
            data_layer.registered_modules[module_name] = collector
            return True

        with mock.patch.object(utils.hub_connection, "download_module", side_effect=download) as download_module:
            configuration, _, errors = self._validate(PIPELINE)
        self.assertEqual(errors, {})
        download_module.assert_called_once_with(module_name="outputs.test.collector_1", version=1)
        self.assertIsInstance(configuration[1], Collector.Configuration)

    def test_a_failed_download_is_reported(self):
        os.environ["AUTO_DOWNLOAD"] = "1"
        del data_layer.registered_modules["outputs.test.collector_1"]
        with mock.patch.object(utils.hub_connection, "download_module", return_value=False):
            _, _, errors = self._validate(PIPELINE)
        self.assertIn("communication with the hub has failed", errors["collector"][0])

    def test_an_invalid_parameter_is_reported_under_the_id_of_its_module(self):
        _, _, errors = self._validate([dict(PIPELINE[1], panel="panel-9")])
        self.assertEqual(list(errors), ["collector"])
        self.assertIn("'panel'", errors["collector"][0])

    def test_unknown_parameters_are_ignored(self):
        with self.assertLogs("collectu.configuration", level="WARNING") as logs:
            configuration, _, errors = self._validate([PIPELINE[0], dict(PIPELINE[1], colour="red")])
        self.assertEqual(errors, {})
        self.assertFalse(hasattr(configuration[1], "colour"))
        self.assertIn("Unknown key 'colour'", logs.output[0])

    def test_errors_of_the_configuration_as_a_whole_are_reported(self):
        content = [dict(PIPELINE[0], links=["collector", "missing"]), PIPELINE[1]]
        configuration, _, errors = self._validate(content)
        self.assertEqual(errors, {"source": ["A linked module with the id 'missing' does not exist."]})
        self.assertEqual([module.id for module in configuration], ["collector"],
                         "The module with the error is left out, the others are kept.")

    def test_a_secret_removed_by_the_hub_is_reported(self):
        content = [module_config("client", "inputs.test.client_1", host=config.SECRET_PLACEHOLDER)]
        _, _, errors = self._validate(content)
        self.assertIn("'host'", errors["client"][0])
        self.assertIn("removed by the hub", errors["client"][0])

    def test_a_module_without_a_configuration_class_is_reported(self):
        data_layer.registered_modules["outputs.test.bare_1"] = type("OutputModule", (), {"version": 1})
        _, _, errors = self._validate([{"id": "bare", "module_name": "outputs.test.bare_1", "version": 1}])
        self.assertIn("Could not find the configuration class", errors["bare"][0])

    def test_a_module_without_a_name_is_reported(self):
        _, _, errors = self._validate([{"id": "nameless", "version": 1}])
        self.assertEqual(list(errors), ["nameless"])


class TestLoadConfiguration(AppTestCase):
    """
    Loading a configuration replaces the running one - unless it is invalid, in which case nothing changes.
    """

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()

    def test_a_valid_configuration_is_started(self):
        errors = self.configuration.load_configuration_from_stream(json.dumps(PIPELINE))

        self.assertEqual(errors, {})
        self.assertEqual(set(data_layer.module_data), {"source", "collector"})
        self.assertIsInstance(instance("collector"), Collector)
        self.assertTrue(wait_for(lambda: instance("source").started.is_set() and
                                         instance("collector").started.is_set()))
        self.assertEqual(self.configuration.configuration_dict, PIPELINE)
        self.assertEqual([module.id for module in self.configuration.configuration], ["source", "collector"])

    def test_a_loaded_configuration_is_kept_as_an_autosave(self):
        self.configuration.load_configuration_from_stream(json.dumps(PIPELINE))

        task = self.configuration.database_queue.get_nowait()
        self.assertEqual((task["task"], task["autosave"], task["configuration"]), ("add", True, PIPELINE))
        self.assertTrue(task["title"].startswith("autosave ("))

    def test_an_invalid_configuration_leaves_the_running_one_alone(self):
        self.configuration.load_configuration_from_stream(json.dumps(PIPELINE))
        running = dict(data_layer.module_data)
        self.configuration.database_queue.get_nowait()

        errors = self.configuration.load_configuration_from_stream(json.dumps([dict(PIPELINE[0], links=["missing"])]))

        self.assertIn("source", errors)
        self.assertEqual(data_layer.module_data, running)
        self.assertTrue(all(entry.instance.active for entry in running.values()))
        self.assertEqual(self.configuration.configuration_dict, PIPELINE)
        self.assertTrue(self.configuration.database_queue.empty(), "An invalid configuration is no autosave.")

    def test_loading_replaces_the_running_configuration(self):
        self.configuration.load_configuration_from_stream(json.dumps(PIPELINE))
        previous = [entry.instance for entry in data_layer.module_data.values()]

        replacement = [module_config("source_2", "inputs.test.source_1.variable", links=["collector_2"]),
                       module_config("collector_2", "outputs.test.collector_1")]
        self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(replacement)), {})

        self.assertEqual(set(data_layer.module_data), {"source_2", "collector_2"})
        self.assertTrue(all(not module.active for module in previous), "The previous modules were not stopped.")

    def test_the_configuration_can_not_be_assigned(self):
        with self.assertLogs("collectu.configuration", level="ERROR"):
            self.configuration.configuration = []
            self.configuration.configuration_dict = []
        self.assertEqual(self.configuration.configuration, [])

    def test_a_file_is_loaded_from_the_configuration_directory(self):
        self.write_configuration_file("line_3/press.yml", yaml.dump(PIPELINE))

        self.assertEqual(self.configuration.load_configuration_from_file("line_3/press.yml"), {})
        self.assertEqual(set(data_layer.module_data), {"source", "collector"})

    def test_the_file_named_in_the_settings_is_loaded_by_default(self):
        self.write_configuration_file("press.yml", yaml.dump(PIPELINE))
        os.environ["CONFIG"] = "press.yml"

        self.assertEqual(self.configuration.load_configuration_from_file(), {})
        self.assertEqual(set(data_layer.module_data), {"source", "collector"})

    def test_a_missing_file_is_reported(self):
        errors = self.configuration.load_configuration_from_file("missing.yml")
        self.assertEqual(list(errors), ["-"])
        self.assertIn("Failed to load configuration file 'missing.yml'", errors["-"][0])

    def test_a_file_outside_the_configuration_directory_is_not_read(self):
        with open(os.path.join(self.root, "outside.yml"), "w", encoding="utf-8") as file:
            file.write(yaml.dump(PIPELINE))

        errors = self.configuration.load_configuration_from_file("../outside.yml")

        self.assertIn("outside the configuration directory", errors["-"][0])
        self.assertEqual(data_layer.module_data, {})


class TestAutoStart(AppTestCase):
    """
    With AUTO_START, the configuration file named in the settings is started as soon as the app is.
    """

    def setUp(self):
        super().setUp()
        os.environ["AUTO_START"] = "1"
        os.environ["CONFIG"] = "press.yml"

    def test_the_configuration_file_is_started_on_creation(self):
        self.write_configuration_file("press.yml", yaml.dump(PIPELINE))
        self.create_configuration()
        self.assertEqual(set(data_layer.module_data), {"source", "collector"})

    def test_an_invalid_configuration_file_is_reported_and_nothing_is_started(self):
        self.write_configuration_file("press.yml", yaml.dump([dict(PIPELINE[0], links=["missing"])]))
        with self.assertLogs("collectu.configuration", level="CRITICAL"):
            self.create_configuration()
        self.assertEqual(data_layer.module_data, {})

    def test_without_auto_start_nothing_is_started(self):
        os.environ["AUTO_START"] = "0"
        self.write_configuration_file("press.yml", yaml.dump(PIPELINE))
        self.create_configuration()
        self.assertEqual(data_layer.module_data, {})


class TestSaveConfiguration(AppTestCase):
    """
    Saving writes a valid configuration as yaml into the configuration directory.
    """

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()

    def _read(self, filename: str):
        with open(os.path.join(self.root, "configuration", filename), encoding="utf-8") as file:
            return yaml.safe_load(file)

    def test_the_content_is_saved_as_yaml(self):
        success, message = self.configuration.save_configuration_as_file("saved.yml", json.dumps(PIPELINE))
        self.assertTrue(success, message)
        self.assertEqual(self._read("saved.yml"), PIPELINE)

    def test_without_content_the_running_configuration_is_saved(self):
        self.configuration.load_configuration_from_stream(json.dumps(PIPELINE))
        success, message = self.configuration.save_configuration_as_file("saved.yml")
        self.assertTrue(success, message)
        self.assertEqual(self._read("saved.yml"), PIPELINE)

    def test_without_a_filename_the_file_named_in_the_settings_is_written(self):
        os.environ["CONFIG"] = "default.yml"
        success, message = self.configuration.save_configuration_as_file(content=json.dumps(PIPELINE))
        self.assertTrue(success, message)
        self.assertEqual(self._read("default.yml"), PIPELINE)

    def test_subdirectories_are_created(self):
        success, message = self.configuration.save_configuration_as_file("line_3/press.yml", json.dumps(PIPELINE))
        self.assertTrue(success, message)
        self.assertEqual(self._read("line_3/press.yml"), PIPELINE)

    def test_an_existing_file_is_overwritten(self):
        self.write_configuration_file("saved.yml", "[]")
        self.configuration.save_configuration_as_file("saved.yml", json.dumps(PIPELINE))
        self.assertEqual(self._read("saved.yml"), PIPELINE)

    def test_an_invalid_configuration_is_not_saved(self):
        content = json.dumps([dict(PIPELINE[0], links=["missing"])])
        self.assertEqual(self.configuration.save_configuration_as_file("saved.yml", content),
                         (False, "The given content is not a valid configuration."))
        self.assertFalse(os.path.exists(os.path.join(self.root, "configuration", "saved.yml")))

    def test_a_file_outside_the_configuration_directory_is_not_written(self):
        settings = os.path.join(self.root, "settings.ini")
        with open(settings, "w", encoding="utf-8") as file:
            file.write("[env]\n")

        success, message = self.configuration.save_configuration_as_file("../settings.ini", json.dumps(PIPELINE))

        self.assertFalse(success)
        self.assertIn("outside the configuration directory", message)
        with open(settings, encoding="utf-8") as file:
            self.assertEqual(file.read(), "[env]\n")

    def test_a_saved_configuration_loads_again(self):
        self.configuration.save_configuration_as_file("saved.yml", json.dumps(PIPELINE))
        self.assertEqual(self.configuration.load_configuration_from_file("saved.yml"), {})
        self.assertEqual(self.configuration.configuration_dict, PIPELINE)

    def test_a_file_which_could_not_be_written_completely_is_removed(self):
        with mock.patch.object(yaml, "dump", side_effect=OSError("No space left on device.")):
            success, message = self.configuration.save_configuration_as_file("saved.yml", json.dumps(PIPELINE))
        self.assertFalse(success)
        self.assertIn("No space left on device.", message)
        self.assertFalse(os.path.exists(os.path.join(self.root, "configuration", "saved.yml")))


class TestConfigurationLibrary(AppTestCase):
    """
    The configurations saved in this app, and the autosaves of the ones it ran. Changed through the database queue,
    which a worker thread works off.
    """

    def setUp(self):
        super().setUp()
        self.configuration = self.create_configuration()

    def _queue(self, **task):
        self.configuration.database_queue.put(task)
        self.work_off_database_queue(self.configuration)

    def _insert(self, entry_id: str, updated_at: str, autosave: bool):
        self.configuration.config_db.insert({"id": entry_id, "title": entry_id, "version": 1, "public": True,
                                             "created_at": updated_at, "updated_at": updated_at, "valid": True,
                                             "autosave": autosave, "description": "", "modules": 0,
                                             "configuration": []})

    def test_loading_a_configuration_adds_an_autosave(self):
        self.configuration.load_configuration_from_stream(json.dumps(PIPELINE))
        self.work_off_database_queue(self.configuration)

        (entry,) = self.configuration.get_database_entries()
        self.assertTrue(entry["autosave"])
        self.assertTrue(entry["valid"])
        self.assertEqual(entry["modules"], 2)
        self.assertEqual(entry["configuration"], PIPELINE)

    def test_an_entry_is_added_with_defaults(self):
        self._queue(task="add", id="a", configuration=PIPELINE)

        entry = self.configuration.get_database_entries(config_id="a")
        self.assertEqual({key: entry[key] for key in ("title", "version", "public", "valid", "autosave",
                                                      "description", "modules")},
                         {"title": "unnamed", "version": 1, "public": True, "valid": True, "autosave": False,
                          "description": "", "modules": 2})

    def test_an_invalid_configuration_is_stored_as_invalid(self):
        self._queue(task="add", id="a", configuration=[dict(PIPELINE[0], links=["missing"])])
        self.assertFalse(self.configuration.get_database_entries(config_id="a")["valid"])

    def test_the_task_name_is_not_case_sensitive(self):
        self._queue(task=" ADD ", id="a", configuration=PIPELINE)
        self.assertIsNotNone(self.configuration.get_database_entries(config_id="a"))

    def test_an_entry_is_updated(self):
        self._queue(task="add", id="a", title="first", configuration=[])
        created = self.configuration.get_database_entries(config_id="a")

        self._queue(task="update", id="a", title="second", configuration=PIPELINE)

        entry = self.configuration.get_database_entries(config_id="a")
        self.assertEqual((entry["title"], entry["modules"], entry["valid"]), ("second", 2, True))
        self.assertEqual(entry["created_at"], created["created_at"])
        self.assertGreaterEqual(entry["updated_at"], created["updated_at"])
        self.assertEqual(entry["description"], created["description"], "What was not given is not changed.")

    def test_every_attribute_of_an_entry_can_be_updated(self):
        self._queue(task="add", id="a", configuration=[])

        self._queue(task="update", id="a", description="Line 3.", public=False, version=4, autosave=True)

        entry = self.configuration.get_database_entries(config_id="a")
        self.assertEqual((entry["description"], entry["public"], entry["version"], entry["autosave"]),
                         ("Line 3.", False, 4, True))

    def test_updating_an_unknown_entry_is_reported(self):
        with self.assertLogs("collectu.configuration", level="WARNING") as logs:
            self._queue(task="update", id="missing", title="second")
        self.assertIn("Could not find entry with the id 'missing'", logs.output[0])

    def test_an_entry_is_deleted(self):
        self._queue(task="add", id="a", configuration=[])
        self._queue(task="delete", id="a")
        self.assertIsNone(self.configuration.get_database_entries(config_id="a"))

    def test_deleting_an_unknown_entry_is_reported(self):
        with self.assertLogs("collectu.configuration", level="WARNING") as logs:
            self._queue(task="delete", id="missing")
        self.assertIn("Could not find entry with the id 'missing'", logs.output[0])

    def test_an_unknown_task_is_reported(self):
        with self.assertLogs("collectu.configuration", level="ERROR") as logs:
            self._queue(task="rename", id="a")
        self.assertIn("Unknown task in database query: rename", logs.output[0])

    def test_only_the_newest_autosaves_are_kept(self):
        self.patch_config(AUTOSAVE_NUMBER=3)
        for day in range(1, 6):
            self._insert(f"autosave_{day}", f"2026-01-0{day}T00:00:00+00:00", autosave=True)
        self._insert("saved", "2025-01-01T00:00:00+00:00", autosave=False)

        # The autosaves are pruned after every task, even one that failed.
        with self.assertLogs("collectu.configuration", level="WARNING"):
            self._queue(task="delete", id="nothing")

        self.assertEqual({entry["id"] for entry in self.configuration.get_database_entries()},
                         {"autosave_3", "autosave_4", "autosave_5", "saved"})

    def test_saved_configurations_are_listed_before_the_autosaves_and_newest_first(self):
        self._insert("autosave_old", "2026-01-01T00:00:00+00:00", autosave=True)
        self._insert("saved_old", "2026-01-02T00:00:00+00:00", autosave=False)
        self._insert("autosave_new", "2026-01-03T00:00:00+00:00", autosave=True)
        self._insert("saved_new", "2026-01-04T00:00:00+00:00", autosave=False)

        self.assertEqual([entry["id"] for entry in self.configuration.get_database_entries()],
                         ["saved_new", "saved_old", "autosave_new", "autosave_old"])

    def test_timestamps_are_converted_on_request(self):
        self._insert("a", "2026-01-01T00:00:00+00:00", autosave=False)

        self.assertIsInstance(self.configuration.get_database_entries()[0]["updated_at"], str)
        for entry in (self.configuration.get_database_entries(convert_timestamps=True)[0],
                      self.configuration.get_database_entries(convert_timestamps=True, config_id="a")):
            self.assertEqual(entry["created_at"].year, 2026)
            self.assertEqual(entry["updated_at"].tzinfo.utcoffset(None).total_seconds(), 0)

    def test_an_unknown_id_has_no_entry(self):
        self.assertIsNone(self.configuration.get_database_entries(config_id="missing"))
        self.assertIsNone(self.configuration.get_database_entries(convert_timestamps=True, config_id="missing"))


if __name__ == '__main__':
    unittest.main()
