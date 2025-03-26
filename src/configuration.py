"""
The configuration class.
"""
from datetime import datetime, timezone
import os
import copy
import logging
import time
import pathlib
import uuid
from collections import defaultdict
from typing import Any, Union, Optional
from pprint import pformat
import queue
import threading
import inspect

# Internal imports.
import config
import data_layer
import models
from models.validations import ValidationError
import utils.hub_connection

# Third party imports.
import json

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)

# Third-party imports (optional).
try:
    import yaml
except ImportError as e:
    yaml = None
    logger.error("Optional yaml package not installed! Some features may not be supported.")

try:
    import tinydb
except ImportError as e:
    tinydb = None
    logger.error("Optional tinydb package not installed! Some features may not be supported.")


class Configuration:
    """
    The configuration class.
    """

    def __init__(self):
        data_layer.configuration = self
        """Add self to data layer."""
        self._configuration: list[models.Module] = []
        """The deserialized configuration (with defaults)."""
        self._configuration_dict: list[dict] = []
        """The configuration as dictionary (without defaults)."""

        # Create directory for the database if it does not exist.
        pathlib.Path(os.path.join('..', 'data', 'configuration')).mkdir(parents=True, exist_ok=True)
        # Instantiate the database.
        self.config_db = tinydb.TinyDB(
            os.path.join('..', 'data', 'configuration', 'configuration.db')) if tinydb else {}
        """The configuration database."""
        self.database_queue: queue.Queue = queue.Queue()
        """A queue with tasks for the database worker. 
        Allowed queue content: 
        - {"task": "add", "configuration": list_of_dicts, "description": "string", "autosave": True/False}
        - {"task": "update", "id": "id", "configuration": list_of_dicts, "description": "string", "autosave": True/False}
        - {"task": "delete", "id": "id"}"""

        # Start the queue processing for storing incoming data.
        threading.Thread(target=self._database_worker,
                         daemon=True,
                         name="Queue_Configuration_Database_Worker").start()

        # Auto start the default configuration (configuration.yaml) if AUTO_START is enabled.
        if bool(int(os.environ.get('AUTO_START', '1'))):
            errors = self.load_configuration_from_file()
            if errors:
                logger.critical("Could not load and start the configuration. "
                                "Please fix the configuration file and reload it.")
                logger.critical("The following errors occurred while trying to "
                                "deserialize the configuration:\n" +
                                "\n".join("{}: {}".format(k, v) for k, v in errors.items()))

    @property
    def configuration(self) -> list[Any]:
        """
        Get the current configuration.

        :returns: The current configuration.
        """
        return self._configuration

    @configuration.setter
    def configuration(self, configuration: list[Any]):
        """
        The setter for the configuration.

        :param configuration: The configuration.
        """
        logger.error("You can not set the configuration like this. "
                     "Please use: load_configuration_from_stream.")

    @configuration.deleter
    def configuration(self):
        """
        The deleter for the configuration.
        """
        self.stop()

    @property
    def configuration_dict(self) -> list[dict]:
        """
        Get the current configuration as list of dicts.

        :returns: The current configuration.
        """
        return self._configuration_dict

    @configuration_dict.setter
    def configuration_dict(self, configuration_dict: list[dict]):
        """
        The setter for the configuration_dict.

        :param configuration_dict: The configuration_dict.
        """
        logger.error("You can not set the configuration_dict like this. "
                     "Please use: load_configuration_from_stream.")

    @configuration_dict.deleter
    def configuration_dict(self):
        """
        The deleter for the configuration_dict.
        """
        self.stop()

    def _database_worker(self):
        """
        The queue worker for interacting with the configuration database.

        The last config.AUTOSAVE_NUMBER elements are stored if a configuration is loaded.
        """
        while data_layer.running:
            try:
                try:
                    # The timeout is needed so we can check if the app should still run.
                    data = self.database_queue.get(block=True, timeout=1)
                    self.database_queue.task_done()
                except queue.Empty:
                    continue

                task = data.get("task", None)
                task = task.lower().strip() if task is not None else None
                # Get the additional attributes.
                configuration = data.get("configuration", None)
                description = data.get("description", None)
                title = data.get("title", None)
                version = data.get("version", None)
                public = data.get("public", None)
                autosave = data.get("autosave", None)
                config_id = data.get("id", str(uuid.uuid4()))

                if task == "add":
                    if configuration is None:
                        configuration = []

                    try:
                        _, _, errors = self.validate_configuration_from_stream(str(configuration))
                        if errors:
                            valid = False
                        else:
                            valid = True
                    except Exception:
                        valid = False

                    entry = {"id": config_id,
                             "title": title if title is not None else "unnamed",
                             "version": int(version) if version is not None else 1,
                             "public": public if public is not None else True,
                             "created_at": datetime.now(timezone.utc).isoformat(),
                             "updated_at": datetime.now(timezone.utc).isoformat(),
                             "valid": valid,
                             "autosave": autosave if autosave is not None else False,
                             "description": description if description is not None else "",
                             "modules": len(configuration),
                             "configuration": configuration}
                    if tinydb:
                        self.config_db.insert(entry)
                    else:
                        self.config_db[config_id] = entry
                    logger.debug("Added entry with the id '{0}' to configuration database.".format(config_id))

                elif task == "update":
                    update_dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
                    if description is not None:
                        update_dict["description"] = description
                    if title is not None:
                        update_dict["title"] = title
                    if public is not None:
                        update_dict["public"] = public
                    if version is not None:
                        update_dict["version"] = version
                    if configuration is not None:
                        update_dict["configuration"] = configuration
                        update_dict["modules"] = len(configuration)
                        try:
                            _, _, errors = self.validate_configuration_from_stream(str(configuration))
                            if errors:
                                update_dict["valid"] = False
                            else:
                                update_dict["valid"] = True
                        except Exception:
                            update_dict["valid"] = False
                    if autosave is not None:
                        update_dict["autosave"] = autosave

                    if tinydb:
                        updates = self.config_db.update(update_dict, tinydb.where('id') == config_id)
                    elif config_id in self.config_db:
                        updates = [1]
                        self.config_db[config_id].update(update_dict)
                    else:
                        updates = []

                    if len(updates) > 0:
                        logger.debug("Updated entry with the id '{0}' in configuration database.".format(config_id))
                    else:
                        logger.warning("Could not update entry in configuration database. "
                                       "Could not find entry with the id '{0}'.".format(config_id))
                elif task == "delete":
                    if tinydb:
                        removals = self.config_db.remove(tinydb.where('id') == config_id)
                    elif config_id in self.config_db:
                        self.config_db.pop(config_id)
                        removals = [1]
                    else:
                        removals = []
                    if len(removals) > 0:
                        logger.debug("Removed entry with the id '{0}' from configuration database."
                                     .format(config_id))
                    else:
                        logger.warning("Could not remove entry in configuration database. "
                                       "Could not find entry with the id '{0}'.".format(config_id))
                elif task is not None:
                    logger.error("Unknown task in database query: {0}".format(task))

                # Check the number of autosave elements (config.AUTOSAVE_NUMBER) and remove the oldest ones,
                # if we have more.
                if tinydb:
                    while len(self.config_db.search(tinydb.where('autosave') == True)) > config.AUTOSAVE_NUMBER:
                        oldest_element = min(self.config_db.search(tinydb.where('autosave') == True),
                                             key=lambda x: x['updated_at'])
                        self.config_db.remove(tinydb.where('id') == oldest_element.get("id"))
                        logger.debug("Removed oldest autosave element from configuration database.")
                else:
                    autosave_entries = {k: v for k, v in self.config_db.items() if v.get("autosave")}
                    while len(autosave_entries) > config.AUTOSAVE_NUMBER:
                        oldest_key = min(autosave_entries, key=lambda k: autosave_entries[k]["updated_at"])
                        del self.config_db[oldest_key]
                        del autosave_entries[oldest_key]
                        logger.debug("Removed oldest autosave element from configuration database.")

            except Exception as e:
                logger.error("Something went wrong while trying to interact with the configuration database: {0}"
                             .format(str(e)), exc_info=config.EXC_INFO)

    def get_database_entries(self,
                             convert_timestamps: bool = False,
                             config_id: str = None) -> Union[list[dict], Optional[dict]]:
        """
        Get all entries of the configuration database.

        An entry looks like the following:

        {
            "id": str,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "valid": True/False,
            "autosave": True/False,
            "description": str,
            "title": str,
            "version": int,
            "public": True/False,
            "modules": int,
            "configuration": configuration_dict
        }

        :param convert_timestamps: Convert the timestamps to be datetime.
        :param config_id: The id of a specific database entry.

        :returns: All database entries or exactly one if requested with id (can be None if id was not found).
        """
        if config_id is not None:
            entry = self.config_db.get(tinydb.where('id') == config_id) if tinydb else self.config_db.get(config_id,
                                                                                                          None)
            if entry is not None and convert_timestamps:
                entry["created_at"] = datetime.fromisoformat(entry["created_at"])
                entry["updated_at"] = datetime.fromisoformat(entry["updated_at"])
            return entry
        else:
            entries = self.config_db.all() if tinydb else self.config_db.values()
            # Sort by updated_at and autosave.
            entries = sorted(entries, key=lambda i: (not i['autosave'], i['updated_at']), reverse=True)
            # Convert the timestamps to be datetime.
            if convert_timestamps:
                for entry in entries:
                    entry["created_at"] = datetime.fromisoformat(entry["created_at"])
                    entry["updated_at"] = datetime.fromisoformat(entry["updated_at"])
            return entries

    def load_configuration_from_file(self, filename: str = None) -> dict[str, list[str]]:
        """
        Loads the given yaml or json file from /configuration and deserializes it using the configuration model.
        If no filename is given, the filename defined in the environment variable 'CONFIG' is used.
        The deserialized configuration will be automatically executed.

        :param filename: The filename (including file extension) to be loaded.

        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        errors = {}
        try:
            if not filename:
                filename = os.environ.get('CONFIG', 'configuration.yml')
            # Set the path to the file.
            file = os.path.join('..', 'configuration', filename)
            # Read the file.
            with open(file) as content:
                content = content.read().strip()
            logger.info(f'Loading configuration from {filename}.')
            # Load the configuration file defined in the environment variable.
            errors = self.load_configuration_from_stream(content=content)
        except Exception as e:
            errors = {"-": ["Failed to load configuration file '{0}': {1}".format(filename, str(e))]}
        finally:
            return errors

    def load_configuration_from_stream(self, content: str) -> dict[str, list[str]]:
        """
        Deserializes the given stream using the configuration model.
        Possible validation errors are included in the returned error dictionary.
        The deserialized configuration will be automatically executed if no errors occurred.

        :param content: The content of the configuration as yaml or json.

        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        errors = {}
        try:
            configuration, configuration_dict, errors = self.validate_configuration_from_stream(content)
            if not errors:
                # Set the configuration attributes.
                self._configuration = configuration
                self._configuration_dict = configuration_dict
                self.restart()

                self.database_queue.put({"task": "add",
                                         "configuration": copy.deepcopy(configuration_dict),
                                         "description": "autosave",
                                         "title": f"autosave ({datetime.now(timezone.utc).replace(microsecond=0)})",
                                         "valid": True,
                                         "autosave": True})

                # This prints the complete configuration file.
                logger.debug("Deserialized configuration:\n" + pformat(configuration))
                logger.info("Successfully set new configuration.")
        except Exception as e:
            errors = {"-": ["Failed to process configuration stream: {0}".format(str(e))]}
        finally:
            return errors

    @staticmethod
    def validate_configuration_from_stream(content: str) -> tuple[list, list, dict[str, list[str]]]:
        """
        Deserializes the given stream using the configuration model.
        Possible validation errors are included in the returned error dictionary.
        The deserialized configuration will not be executed!

        :param content: The content of the configuration as yaml or json.

        :returns: The configuration as deserialized configuration,
                  as list of dicts, where the default attributes are not included,
                  and a dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        configuration = []
        configuration_dict = []
        errors = defaultdict(list)
        try:
            if yaml:
                configuration_dict = yaml.load(stream=content, Loader=yaml.FullLoader)
            else:
                logger.warning("Yaml package is not installed. Trying to deserialize content using json...")
                try:
                    configuration_dict = json.loads(content)
                except Exception as e:
                    raise Exception("Content seems not to be a valid json.")

            # If the file was empty, we create a default value.
            if not configuration_dict:
                configuration_dict = []

            for module_configuration in configuration_dict:
                try:
                    # Get the correct dataclass in accordance to the module_name.
                    module_name = module_configuration.get("module_name").lower()
                    version = module_configuration.get("version", None)
                    module = data_layer.registered_modules.get(module_name, None)
                    not_found = False
                    if module is None:
                        logger.info("Module '{0}' does not exist locally.".format(module_name))
                        not_found = True
                    elif getattr(module, "version", None) != version:
                        logger.info("Module '{0}' with version '{1}' does not exist locally. "
                                    "Your current version is: {2}."
                                    .format(module_name, str(version), str(getattr(module, "version", "unknown"))))
                        not_found = True
                    if not_found:
                        if not bool(int(os.environ.get('AUTO_DOWNLOAD', '0'))):
                            logger.error("Could not automatically search and download '{0}', "
                                         "since auto_download is disabled in your settings.ini file"
                                         .format(module_name))
                            errors[module_configuration.get("id", "-")].append(f"Unknown module_name '{module_name}' "
                                                                               f"or version '{version}'.")
                            continue
                        # Try to fetch the module from hub.
                        elif not utils.hub_connection.download_module(module_name=module_name, version=version):
                            errors[module_configuration.get("id", "-")].append(
                                f"Unknown module_name '{module_name}', version '{version}', "
                                f"or communication with the hub has failed for other reasons. Please check the logs.")
                            continue
                        else:
                            module = data_layer.registered_modules.get(module_name, None)
                    # Deserialize the module configuration using the according dataclass
                    # and add it to the configuration list.
                    module_schema = getattr(module, "Configuration", None)
                    if module_schema is not None:
                        configuration.append(module_schema(**module_configuration))
                    else:
                        errors[module_configuration.get("id", "-")].append(
                            "Invalid module. Could not find the configuration class. Please make sure the used "
                            "module contains a configuration definition.")
                except ValidationError as e:
                    errors[module_configuration.get("id", "-")].extend(e.args[0])
                except (ValueError, TypeError) as e:
                    # E.g. unexpected keywords in the configuration.
                    errors[module_configuration.get("id", "-")].append(f"Invalid configuration: {e}")
                except Exception as e:
                    errors[module_configuration.get("id", "-")].append(f"Something unexpected went wrong while trying "
                                                                       f"to deserialize configuration: {e}")

            # Configuration level validations.
            for module_id, error_list in models.validations.validate_configuration(configuration).items():
                errors[module_id].extend(error_list)

            # Pop the modules from the configuration list, for which an error occurred.
            configuration = [module_config for module_config in configuration if module_config.id not in errors]

        except Exception as e:
            configuration = []
            configuration_dict = []
            errors = {"-": ["Failed to validate configuration: {0}".format(str(e))]}
        finally:
            # Make a 'normal' dict from the defaultdict().
            errors = dict(errors.items())
            return configuration, configuration_dict, errors

    def _start(self):
        """
        Start the execution of the current configuration.
        Only modules, which are not currently running are started.
        """
        logger.info("Starting configuration start routine...")
        self._create_buffer_module()
        self._create_output_modules()
        self._create_processor_modules()
        self._create_input_modules()
        self._create_tag_modules()
        self._create_variable_modules()
        logger.info("Finished configuration start routine (started {0} modules).".format(len(self.configuration_dict)))

    def restart(self):
        """
        Restart the current configuration.
        The module_data is reset.
        """
        self.stop()
        self._start()

    @staticmethod
    def _stop_module(module_data):
        """
        Call the stop method of a given module.
        This method should be called in a separate thread.

        :param module_data: The module data.
        """
        try:
            logger.debug("Trying to stop module '{0}' with the id '{1}'."
                         .format(module_data.module_name, module_data.configuration.id))
            module_data.instance.active = False
            module_data.instance.stop()
        except Exception as e:
            logger.error("Could not stop module '{0}' with the id '{1}': {2}"
                         .format(module_data.module_name, module_data.configuration.id,
                                 str(e)), exc_info=config.EXC_INFO)

    def stop(self):
        """
        Stop the execution of a configuration. Everything is reset.
        """
        try:
            if data_layer.module_data:
                # Print a message that we stopped modules, if we actually stopped modules.
                logger.info("Starting configuration stop routine...")

            # Stop all variable modules by setting self.active to false and calling the stop method.
            filtered_dict = {k: v for k, v in data_layer.module_data.items() if
                             v.module_name.endswith(".variable") and v.module_name.startswith("inputs.")}
            sorted_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1].configuration.start_priority))
            for module_id, module_data in sorted_dict.items():
                threading.Thread(target=self._stop_module, args=(module_data,), daemon=True).start()

            # Now, no new data should be generated.
            # Wait a little, until all pipelines have executed.
            # However, this does not guarantee all pipelines finished.
            # In case a pipeline hasn't finished, an error message is (probably) generated.
            time.sleep(0.5)

            # Stop all tag modules.
            filtered_dict = {k: v for k, v in data_layer.module_data.items() if
                             v.module_name.endswith(".tag") and v.module_name.startswith("inputs.")}
            sorted_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1].configuration.start_priority))
            for module_id, module_data in sorted_dict.items():
                threading.Thread(target=self._stop_module, args=(module_data,), daemon=True).start()

            # Stop all input modules.
            filtered_dict = {k: v for k, v in data_layer.module_data.items() if
                             v.module_name.startswith("inputs.") and not v.module_name.endswith(
                                 ".variable") and not v.module_name.endswith(".tag")}
            sorted_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1].configuration.start_priority))
            for module_id, module_data in sorted_dict.items():
                threading.Thread(target=self._stop_module, args=(module_data,), daemon=True).start()

            # Stop all processor modules.
            filtered_dict = {k: v for k, v in data_layer.module_data.items() if
                             v.module_name.startswith("processors.")}
            sorted_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1].configuration.start_priority))
            for module_id, module_data in sorted_dict.items():
                threading.Thread(target=self._stop_module, args=(module_data,), daemon=True).start()

            # Stop all output modules.
            filtered_dict = {k: v for k, v in data_layer.module_data.items() if
                             v.module_name.startswith("outputs.")}
            sorted_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1].configuration.start_priority))
            for module_id, module_data in sorted_dict.items():
                threading.Thread(target=self._stop_module, args=(module_data,), daemon=True).start()

            # Wait for the stopping threads to finish.
            time.sleep(config.STOP_TIMEOUT)

            if data_layer.module_data:
                # Print a message that we stopped modules, if we actually stopped modules.
                logger.info("Successfully finished configuration stop routine.")
        except Exception as e:
            logger.critical("Something unexpected went wrong while trying to stop modules: {0}"
                            .format(str(e)), exc_info=config.EXC_INFO)
        finally:
            # Reset buffer instance.
            data_layer.buffer_instance = None
            # Reset module data.
            data_layer.module_data = {}
            # Reset the dashboard modules.
            data_layer.dashboard_modules = []

    def update_configuration(self, content: str) -> dict[str, list[str]]:
        """
        Update the current configuration. Deleted modules are stopped and new ones are started.

        :param content: A string with module descriptions (json or yaml).
        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        # First we check if the new configuration is valid.
        configuration, configuration_dict, errors = self.validate_configuration_from_stream(content)
        if not errors:
            # Get and remove all changed or removed modules.
            removed_keys = [old_module.get("id", None) for old_module in self._configuration_dict if
                            old_module not in [module for module in configuration_dict]]
            self.remove_modules_from_configuration(removed_keys)

            # Get the configuration of all changed or new modules.
            new_modules = [module for module in configuration_dict if module not in self._configuration_dict]
            self.add_modules_to_configuration(json.dumps(new_modules, default=lambda o: o.__dict__))
        return errors

    def add_modules_to_configuration(self, content: str) -> dict[str, list[str]]:
        """
        Start the execution of defined modules.

        :param content: A string with module descriptions (a valid json or yaml string).
        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        try:
            if yaml:
                configuration_dict = yaml.load(stream=content, Loader=yaml.FullLoader)
            else:
                logger.warning("Yaml package is not installed. Trying to deserialize content using json...")
                try:
                    configuration_dict = json.loads(content)
                except Exception as e:
                    raise Exception("Content seems not to be a valid json.")

            configuration_dict = self._configuration_dict + configuration_dict
            configuration, configuration_dict, errors = self.validate_configuration_from_stream(
                json.dumps(configuration_dict, default=lambda o: o.__dict__))
            if not errors:
                self._configuration = configuration
                self._configuration_dict = configuration_dict
                self._start()
            return errors
        except Exception as e:
            return {"-": ["Could not add modules to configuration: {0}".format(str(e))]}

    def remove_modules_from_configuration(self, module_ids: list[str]) -> dict[str, list[str]]:
        """
        Stop the execution of defined modules.

        :param module_ids: A list of modules ids.
        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        configuration_dict = self._configuration_dict
        # If a given module id does not exist, it is ignored.
        configuration_dict = [module for module in configuration_dict if module.get("id") not in module_ids]
        configuration, configuration_dict, errors = self.validate_configuration_from_stream(
            json.dumps(configuration_dict, default=lambda o: o.__dict__))
        if not errors:
            for module_id in module_ids:
                if module_id in data_layer.module_data:
                    # Check if it is a buffer.
                    if getattr(data_layer.module_data[module_id].configuration, "is_buffer", False):
                        data_layer.buffer_instance = None
                    threading.Thread(target=self._stop_module, args=(data_layer.module_data[module_id],),
                                     daemon=True).start()
                    data_layer.module_data.pop(module_id)

                    for dashboard_module in data_layer.dashboard_modules:
                        if dashboard_module.configuration.id == module_id:
                            data_layer.dashboard_modules.remove(dashboard_module)
            self._configuration = configuration
            self._configuration_dict = configuration_dict
        return errors

    @staticmethod
    def _check_if_deprecated(module) -> bool:
        """
        Checks if the given module is deprecated. If it is, a warning message is logged.

        :param module: The module to be checked.
        :returns: True, if the module is deprecated, else false.
        """
        if getattr(module, "deprecated", False):
            logger.warning("The module '{0}' is deprecated. Please check if a newer module version is available."
                           .format(str(".".join([module.__module__, module.__name__])).replace("modules.", "")))
            return True
        return False

    @staticmethod
    def _start_module(module_config, module_instance):
        """
        Calls the start method of the given module instance.
        Should be called in a separate thread.

        :param module_config: The configuration of the module.
        :param module_instance: The instance of the module.
        """
        retries: int = 0
        while getattr(module_instance, "active", False):
            try:
                module_instance.start()
            except Exception as e:
                logger.error("Could not start module '{0}' with the id '{1}': {2}"
                             .format(module_config.module_name, module_config.id, str(e)),
                             exc_info=config.EXC_INFO)
                time.sleep(config.RETRY_INTERVAL)
                retries += 1
                logger.error("Retrying to start module '{0}' with the id '{1}' in the {2} attempt."
                             .format(module_config.module_name, module_config.id, str(retries)))
            else:
                logger.debug("Successfully started module '{0}' with the id '{1}'."
                             .format(module_config.module_name, module_config.id))
                # The module seems to handle exceptions during the execution by itself,
                # so we never try to restart it.
                break

    @classmethod
    def _create_module(cls, module_config):
        """
        Start the given module.

        :param module_config: The config of the module to be started.
        """
        # Check if this module is already instantiated.
        if module_config.id not in data_layer.module_data:
            try:
                # Get the according module.
                module = data_layer.registered_modules.get(module_config.module_name)
                cls._check_if_deprecated(module)

                # Get the according input module if required.
                input_module_instance = getattr(
                    data_layer.module_data.get(getattr(module_config, "input_module", ""), None),
                    "instance", None)

                if input_module_instance:
                    module_instance = module(configuration=module_config, input_module_instance=input_module_instance)
                else:
                    module_instance = module(configuration=module_config)
                # Check if buffer module.
                if getattr(module_config, "is_buffer", False):
                    data_layer.buffer_instance = module_instance

                # Create an entry in the data layer.
                data_layer.module_data[module_config.id] = models.ModuleData(
                    instance=module_instance,
                    configuration=module_config,
                    module_name=module_config.module_name)

                threading.Thread(target=cls._start_module, args=(module_config, module_instance,), daemon=True).start()
            except ImportError:
                logger.critical("Could not start module '{0}' with the id '{1}'. Import of third party packages failed."
                                .format(module_config.module_name, module_config.id))
            except Exception as e:
                logger.critical("Something unexpected went wrong while trying to start module '{0}' "
                                "with the id '{1}': {2}"
                                .format(module_config.module_name, module_config.id, str(e)),
                                exc_info=config.EXC_INFO)

    def _create_buffer_module(self):
        """
        Instantiate and connect the buffer module if there is one.
        """
        # Get the first buffer configuration if there is one.
        # There should be only one, since we check it during validation.
        buffer_config = next(iter([buffer_config for buffer_config in self._configuration if
                                   getattr(buffer_config, "is_buffer", False)]), None)
        # CAUTION: The start priority has no effect here.
        if buffer_config:
            self._create_module(module_config=buffer_config)

    def _create_output_modules(self):
        """
        Instantiate and connect all output modules.
        """
        output_configs = [output_config for output_config in self._configuration if
                          not getattr(output_config, "is_buffer", False)
                          and output_config.module_name.startswith("outputs.")]
        for output_config in sorted(output_configs,
                                    key=lambda output_config: output_config.start_priority,
                                    reverse=True):
            self._create_module(module_config=output_config)

    def _create_processor_modules(self):
        """
        Create all processor modules.
        """
        processor_configs = [processor_config for processor_config in self._configuration if
                             processor_config.module_name.startswith("processors.")]
        for processor_config in sorted(processor_configs,
                                       key=lambda processor_config: processor_config.start_priority,
                                       reverse=True):
            self._create_module(module_config=processor_config)

    def _create_input_modules(self):
        """
        Instantiate and connect all input modules.
        """
        input_configs = [input_config for input_config in self._configuration if
                         input_config.module_name.startswith("inputs.") and
                         not input_config.module_name.endswith(".variable") and
                         not input_config.module_name.endswith(".tag")]
        for input_config in sorted(input_configs,
                                   key=lambda input_config: input_config.start_priority,
                                   reverse=True):
            self._create_module(module_config=input_config)

    def _create_tag_modules(self):
        """
        Instantiate and connect all tag modules.
        """
        tag_configs = [tag_config for tag_config in self._configuration if
                       tag_config.module_name.endswith(".tag") and
                       tag_config.module_name.startswith("inputs.") and
                       not tag_config.module_name.endswith(".variable")]
        for tag_config in sorted(tag_configs,
                                 key=lambda tag_config: tag_config.start_priority,
                                 reverse=True):
            self._create_module(module_config=tag_config)

    def _create_variable_modules(self):
        """
        Instantiate and connect all variable modules.
        """
        variable_configs = [variable_config for variable_config in self._configuration if
                            variable_config.module_name.endswith(".variable") and
                            variable_config.module_name.startswith("inputs.") and
                            not variable_config.module_name.endswith(".tag")]
        for variable_config in sorted(variable_configs,
                                      key=lambda variable_config: variable_config.start_priority,
                                      reverse=True):
            self._create_module(module_config=variable_config)

    def save_configuration_as_file(self, filename: str = None, content: str = None) -> tuple[bool, str]:
        """
        Create a YAML or JSON configuration file with the given filename and content.
        Caution: If the file already exists, it is overwritten.

        :param filename: The filename of the configuration.
        If no filename is given, the file name, specified in the settings.ini is used (default: configuration.yml).
        :param content: The content of the configuration as yaml or json string.
        If no content is given, the current configuration is saved.

        :returns: A boolean indicating if the saving process was successful and an additional message.
        """
        if not filename:
            filename = os.environ.get('CONFIG', 'configuration.yml')
        if not content:
            content = self._configuration_dict
        # This is the file path including the file name.
        file = os.path.join('..', 'configuration', '{0}').format(filename)
        try:
            # Validate the content.
            configuration, configuration_dict, errors = self.validate_configuration_from_stream(content=content)
            if errors:
                return False, f"The given content is not a valid configuration."
            else:
                # Create directory and file.
                pathlib.Path(os.path.join('..', 'configuration',
                                          str(pathlib.Path(filename).parents[0]))).mkdir(parents=True, exist_ok=True)
                try:
                    # Write content to file.
                    with open(file, 'w') as stream:
                        if yaml:
                            stream.write(f'{yaml.dump(configuration_dict)}')
                        else:
                            logger.warning("Yaml package is not installed. Trying to serialize content using json...")
                            json.dump(configuration_dict, stream, indent=4)
                except Exception as e:
                    try:
                        # Something went wrong, we try to delete the created file.
                        os.remove(file)
                    except Exception:
                        pass
                    return False, f"Could not write to configuration file {filename}. {str(e)}"
                logger.info(f"Successfully saved configuration file {filename}.")
                return True, f"Successfully saved configuration file {filename}."
        except Exception as e:
            return False, f"Could not save configuration file {filename}. {str(e)}"
