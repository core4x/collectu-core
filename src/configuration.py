"""
The configuration class.
"""
import datetime
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

# Internal imports.
import config
import data_layer
import models
from models.validations import ValidationError
import utils.retrying
import utils.hub_connection

# Third party imports.
import yaml
import json
import tinydb

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)


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
        self.retries: list[utils.retrying.RetryStart] = []
        """Contains all established retry classes. They do not have to run anymore."""

        # Create directory for the database if it does not exist.
        pathlib.Path(os.path.join('..', 'data', 'configuration')).mkdir(parents=True, exist_ok=True)
        # Instantiate the database.
        self.config_db = tinydb.TinyDB(os.path.join('..', 'data', 'configuration', 'configuration.db'))
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
                documentation = data.get("documentation", None)
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

                    self.config_db.insert({"id": config_id,
                                           "title": title if title is not None else "unnamed",
                                           "version": version if version is not None else 1,
                                           "documentation": documentation if documentation is not None else "",
                                           "public": public if public is not None else True,
                                           "created_at": datetime.datetime.utcnow().isoformat(),
                                           "updated_at": datetime.datetime.utcnow().isoformat(),
                                           "valid": valid,
                                           "autosave": autosave if autosave is not None else False,
                                           "description": description if description is not None else "",
                                           "modules": len(configuration),
                                           "configuration": configuration})
                    logger.debug("Added entry with the id '{0}' to configuration database.".format(config_id))

                elif task == "update":
                    update_dict = {"updated_at": datetime.datetime.utcnow().isoformat()}
                    if description is not None:
                        update_dict["description"] = description
                    if documentation is not None:
                        update_dict["documentation"] = documentation
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
                    updates = self.config_db.update(update_dict, tinydb.where('id') == config_id)
                    if len(updates) > 0:
                        logger.debug("Updated entry with the id '{0}' in configuration database."
                                     .format("config_id"))
                    else:
                        logger.warning("Could not update entry in configuration database. "
                                       "Could not find entry with the id '{0}'.".format(config_id))
                elif task == "delete":
                    removals = self.config_db.remove(tinydb.where('id') == config_id)
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
                while len(self.config_db.search(tinydb.where('autosave') == True)) > config.AUTOSAVE_NUMBER:
                    oldest_element = min(self.config_db.search(tinydb.where('autosave') == True),
                                         key=lambda x: x['updated_at'])
                    self.config_db.remove(tinydb.where('id') == oldest_element.get("id"))
                    logger.debug("Removed oldest autosave element from configuration database.")

            except Exception as e:
                logger.error("Something went wrong while trying to interact with the configuration database: {0}"
                             .format(str(e)), exc_info=config.EXC_INFO)

    def get_database_entries(self, convert_timestamps: bool = False, config_id: str = None) -> Union[list[dict],
    Optional[dict]]:
        """
        Get all entries of the configuration database.

        An entry looks like the following:

        {
            "id": str,
            "created_at": datetime.datetime.utcnow,
            "updated_at": datetime.datetime.utcnow,
            "valid": True/False,
            "autosave": True/False,
            "description": str,
            "title": str,
            "version": str,
            "documentation": str,
            "public": True/False,
            "modules": int,
            "configuration": configuration_dict
        }

        :param convert_timestamps: Convert the timestamps to be datetime.
        :param config_id: The id of a specific database entry.

        :returns: All database entries or exactly one if requested with id (can be None if id was not found).
        """
        if config_id is not None:
            entry = self.config_db.get(tinydb.where('id') == config_id)
            if entry is not None and convert_timestamps:
                entry["created_at"] = datetime.datetime.fromisoformat(entry["created_at"])
                entry["updated_at"] = datetime.datetime.fromisoformat(entry["updated_at"])
            return entry
        else:
            entries = self.config_db.all()
            # Sort by updated_at and autosave.
            entries = sorted(entries, key=lambda i: (not i['autosave'], i['updated_at']), reverse=True)
            # Convert the timestamps to be datetime.
            if convert_timestamps:
                for entry in entries:
                    entry["created_at"] = datetime.datetime.fromisoformat(entry["created_at"])
                    entry["updated_at"] = datetime.datetime.fromisoformat(entry["updated_at"])
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
                                         "documentation": f"Number of modules: {len(configuration)}",
                                         "title": f"autosave ({datetime.datetime.utcnow().replace(microsecond=0)})",
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
            configuration_dict = yaml.load(stream=content, Loader=yaml.FullLoader)
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

    def _start(self) -> bool:
        """
        Start the execution of the current configuration.
        Only modules, which are not currently running are started.

        :returns: True if the start procedure was successful.
        """
        if bool(int(os.environ.get('TEST', '0'))):
            logger.info("Starting configuration start routine in test mode "
                        "(output modules will not store data and all modules will be stopped after "
                        "the start routine)...")
        else:
            logger.info("Starting configuration start routine...")
        success = True
        success_buffer = self._create_buffer_module()
        success_output = self._create_output_modules()
        success_processor = self._create_processor_modules()
        success_input = self._create_input_modules()
        success_tag = self._create_tag_modules()
        success_variable = self._create_variable_modules()

        # If not every initial connection was successful, we stop all modules (if not IGNORE_START_FAIL).
        if not (success_buffer and
                success_output and
                success_processor and
                success_input and
                success_tag and
                success_variable):
            if not bool(int(os.environ.get('IGNORE_START_FAIL', '0'))):
                logger.critical("Configuration start routine was not successful. Stopping all modules.")
                self.stop()
                success = False
            else:
                unsuccessful_modules = ""
                if not success_buffer:
                    unsuccessful_modules = "buffer" if not unsuccessful_modules else \
                        unsuccessful_modules + ", buffer"
                if not success_output:
                    unsuccessful_modules = "output" if not unsuccessful_modules else \
                        unsuccessful_modules + ", output"
                if not success_processor:
                    unsuccessful_modules = "processor" if not unsuccessful_modules else \
                        unsuccessful_modules + ", processor"
                if not success_input:
                    unsuccessful_modules = "input" if not unsuccessful_modules else \
                        unsuccessful_modules + ", input"
                if not success_tag:
                    unsuccessful_modules = "tag" if not unsuccessful_modules else \
                        unsuccessful_modules + ", tag"
                if not success_variable:
                    unsuccessful_modules = "variable" if not unsuccessful_modules else \
                        unsuccessful_modules + ", variable"
                logger.error("Configuration start routine was not completely successful. "
                             "Could not start all {0} modules.".format(unsuccessful_modules))
        else:
            logger.info("Successfully finished configuration start routine (started {0} modules)."
                        .format(len(self.configuration_dict)))

        # If we are in test mode, we now stop all modules and reset the test flag.
        if bool(int(os.environ.get('TEST', '0'))):
            logger.info("Finished test run.")
            self.stop()
            os.environ['TEST'] = "0"
        return success

    def restart(self) -> bool:
        """
        Restart the current configuration.
        The module_data is reset.

        :returns: True if the restart procedure was successful.
        """
        if self.stop() and self._start():
            return True
        else:
            return False

    def stop(self) -> bool:
        """
        Stop the execution of a configuration. Everything is reset.

        :returns: True if the stop procedure was successful.
        """
        success = True
        try:
            if data_layer.module_data:
                # Print a message that we stopped modules, if we actually stopped modules.
                logger.info("Starting configuration stop routine...")

            # Stop all running retry classes.
            for retry_class in self.retries:
                logger.debug("Trying to stop retry instance: {0}".format(str(retry_class.module.module_name)))
                retry_class.stop()
            self.retries = []

            filtered_dict = {k: v for k, v in data_layer.module_data.items() if
                             v.module_name.endswith(".variable") and v.module_name.startswith("inputs.")}
            sorted_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1].configuration.start_priority))

            # Stop all variable modules by setting self.active to false and calling the stop method.
            for module_id, module_data in sorted_dict.items():
                try:
                    logger.debug("Trying to stop variable module ({0}): {1}"
                                 .format(str(module_id), str(module_data.module_name)))
                    module_data.instance.active = False
                    module_data.instance.stop()
                except Exception as e:
                    success = False
                    logger.error("Could not stop module '{0}' with the id '{1}': {2}"
                                 .format(module_data.module_name,
                                         module_data.configuration.get("id", "-"),
                                         str(e)), exc_info=config.EXC_INFO)
            # Now, no new data should be generated.
            # Wait a little, until all pipelines have executed.
            # However, this does not guarantee all pipelines finished.
            # In case a pipeline hasn't finished, an error message is (probably) generated.
            time.sleep(0.4)

            # Stop all tag modules.
            for module_id, module_data in data_layer.module_data.items():
                if module_data.module_name.startswith("inputs.") and module_data.module_name.endswith(".tag"):
                    try:
                        logger.debug("Trying to stop tag module ({0}): {1}"
                                     .format(str(module_id), str(module_data.module_name)))
                        module_data.instance.active = False
                        module_data.instance.stop()
                    except Exception as e:
                        success = False
                        logger.error("Could not stop module '{0}' with the id '{1}': {2}"
                                     .format(module_data.module_name,
                                             module_data.configuration.get("id", "-"),
                                             str(e)), exc_info=config.EXC_INFO)

            # Stop all input modules.
            for module_id, module_data in data_layer.module_data.items():
                if module_data.module_name.startswith("inputs.") and \
                        not module_data.module_name.endswith(".variable") and \
                        not module_data.module_name.endswith(".tag"):
                    try:
                        logger.debug("Trying to stop input module ({0}): {1}"
                                     .format(str(module_id), str(module_data.module_name)))
                        module_data.instance.active = False
                        module_data.instance.stop()
                    except Exception as e:
                        success = False
                        logger.error("Could not stop module '{0}' with the id '{1}': {2}"
                                     .format(module_data.module_name,
                                             module_data.configuration.get("id", "-"),
                                             str(e)), exc_info=config.EXC_INFO)

            # Stop all processor modules.
            for module_id, module_data in data_layer.module_data.items():
                if module_data.module_name.startswith("processors."):
                    try:
                        logger.debug("Trying to stop processor module ({0}): {1}"
                                     .format(str(module_id), str(module_data.module_name)))
                        module_data.instance.active = False
                        module_data.instance.stop()
                    except Exception as e:
                        success = False
                        logger.error("Could not stop module '{0}' with the id '{1}': {2}"
                                     .format(module_data.module_name,
                                             module_data.configuration.get("id", "-"),
                                             str(e)), exc_info=config.EXC_INFO)

            # Stop all output modules.
            for module_id, module_data in data_layer.module_data.items():
                if module_data.module_name.startswith("outputs."):
                    try:
                        logger.debug("Trying to stop output module ({0}): {1}"
                                     .format(str(module_id), str(module_data.module_name)))
                        module_data.instance.active = False
                        module_data.instance.stop()
                    except Exception as e:
                        success = False
                        logger.error("Could not stop module '{0}' with the id '{1}': {2}"
                                     .format(module_data.module_name,
                                             module_data.configuration.get("id", "-"),
                                             str(e)), exc_info=config.EXC_INFO)

            # Reset buffer instance.
            data_layer.buffer_instance = None
            if data_layer.module_data:
                # Print a message that we stopped modules, if we actually stopped modules.
                logger.info("Successfully finished configuration stop routine.")
            # Reset module data.
            data_layer.module_data = {}
            # Reset the dashboard modules.
            data_layer.dashboard_modules = []
        except Exception as e:
            success = False
        finally:
            return success

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
            configuration_dict = yaml.load(stream=content, Loader=yaml.FullLoader)
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
                    data_layer.module_data[module_id].instance.active = False
                    data_layer.module_data[module_id].instance.stop()
                    data_layer.module_data.pop(module_id)
                    for dashboard_module in data_layer.dashboard_modules:
                        if dashboard_module.configuration.id == module_id:
                            data_layer.dashboard_modules.remove(dashboard_module)
            self._configuration = configuration
            self._configuration_dict = configuration_dict
        return errors

    def _check_if_deprecated(self, module) -> bool:
        """
        Checks if the given module is deprecated. If it is, a warning message is logged.

        :param module: The module to be checked.
        :returns: True, if the module is deprecated, else false.
        """
        if getattr(module, "deprecated", False):
            logger.warning("The module '{0}' is deprecated. Please check if a newer module version is available."
            .format(str(".".join([module.__module__, module.__name__])).replace(
                "modules.", "")))
            return True
        return False

    def _create_buffer_module(self) -> bool:
        """
        Instantiate and connect the buffer module if there is one.

        :returns: Boolean indicating if every module start-up was successful.
        """
        success = True
        try:
            # Get the first buffer configuration if there is one.
            # There should be only one, since we check it during validation.
            buffer_config = next(iter([buffer_config for buffer_config in self._configuration if
                                       getattr(buffer_config, "is_buffer", False)]), None)
            if buffer_config:
                # Check if this module is already instantiated.
                if buffer_config.id not in data_layer.module_data:
                    # Get the according module.
                    buffer_module = data_layer.registered_modules.get(buffer_config.module_name)
                    self._check_if_deprecated(buffer_module)
                    try:
                        data_layer.buffer_instance = buffer_module(configuration=buffer_config)
                        # Create an entry in the data layer.
                        data_layer.module_data[buffer_config.id] = models.ModuleData(
                            instance=data_layer.buffer_instance,
                            configuration=buffer_config,
                            module_name=buffer_config.module_name)
                        if buffer_config.active:
                            if not data_layer.buffer_instance.start():
                                success = False
                                data_layer.buffer_instance = None
                                logger.critical("Could not start buffer module '{0}' with the id '{1}'. "
                                                "Initial connection was not successful. "
                                                "Please check the configuration."
                                                .format(buffer_config.module_name, buffer_config.id))
                                if bool(int(os.environ.get('IGNORE_START_FAIL', '0'))):
                                    self.retries.append(
                                        utils.retrying.RetryStart(module=data_layer.module_data[buffer_config.id]))
                            else:
                                logger.debug("Successfully started buffer module '{0}' with the id '{1}'."
                                             .format(buffer_config.module_name, buffer_config.id))
                    except ImportError:
                        success = False
                        logger.critical("Could not start buffer module '{0}' with the id '{1}'. "
                                        "Import of third party packages failed."
                                        .format(buffer_config.module_name, buffer_config.id))
        except Exception as e:
            logger.critical("{0}".format(str(e)), exc_info=config.EXC_INFO)
            success = False
        finally:
            return success

    def _create_output_modules(self) -> bool:
        """
        Instantiate and connect all output modules.

        :returns: Boolean indicating if every module start-up was successful.
        """
        success = []
        try:
            output_configs = [output_config for output_config in self._configuration if
                              not getattr(output_config, "is_buffer", False) and output_config.module_name.startswith(
                                  "outputs.")]
            for output_config in output_configs:
                # Check if this module is already instantiated.
                if output_config.id not in data_layer.module_data:
                    # Get the according module.
                    output_module = data_layer.registered_modules.get(output_config.module_name)
                    self._check_if_deprecated(output_module)
                    try:
                        output_instance = output_module(configuration=output_config)
                        # Create an entry in the data layer.
                        data_layer.module_data[output_config.id] = models.ModuleData(
                            instance=output_instance,
                            configuration=output_config,
                            module_name=output_config.module_name)
                        if output_config.active:
                            if not output_instance.start():
                                success.append(False)
                                logger.critical("Could not start output module '{0}' with the id '{1}'. "
                                                "Initial connection was not successful. "
                                                "Please check the configuration."
                                                .format(output_config.module_name, output_config.id))
                                if bool(int(os.environ.get('IGNORE_START_FAIL', '0'))):
                                    self.retries.append(
                                        utils.retrying.RetryStart(module=data_layer.module_data[output_config.id]))
                            else:
                                logger.debug("Successfully started output module '{0}' with the id '{1}'."
                                             .format(output_config.module_name, output_config.id))
                    except ImportError:
                        success.append(False)
                        logger.critical("Could not start output module '{0}' with the id '{1}'. "
                                        "Import of third party packages failed."
                                        .format(output_config.module_name, output_config.id))
        except Exception as e:
            logger.critical("{0}".format(str(e)), exc_info=config.EXC_INFO)
            success = False
        finally:
            return True if False not in success else False

    def _create_processor_modules(self) -> bool:
        """
        Create all processor modules.

        :returns: Boolean indicating if every module start-up was successful.
        """
        success = []
        processor_configs = [processor_config for processor_config in self._configuration if
                             processor_config.module_name.startswith("processors.")]
        try:
            for processor_config in processor_configs:
                # Check if this module is already instantiated.
                if processor_config.id not in data_layer.module_data:
                    # Get the according module.
                    processor_module = data_layer.registered_modules.get(processor_config.module_name)
                    self._check_if_deprecated(processor_module)
                    try:
                        processor_instance = processor_module(configuration=processor_config)
                        # Create an entry in the data layer.
                        data_layer.module_data[processor_config.id] = models.ModuleData(
                            instance=processor_instance,
                            configuration=processor_config,
                            module_name=processor_config.module_name)
                        if processor_config.active:
                            if not processor_instance.start():
                                success.append(False)
                                logger.critical("Could not start processor module '{0}' with the id '{1}'. "
                                                "Initial connection was not successful. "
                                                "Please check the configuration."
                                                .format(processor_config.module_name, processor_config.id))
                                if bool(int(os.environ.get('IGNORE_START_FAIL', '0'))):
                                    self.retries.append(
                                        utils.retrying.RetryStart(module=data_layer.module_data[processor_config.id]))
                            else:
                                logger.debug("Successfully started processor module '{0}' with the id '{1}'."
                                             .format(processor_config.module_name, processor_config.id))
                    except ImportError:
                        success.append(False)
                        logger.critical("Could not start processor module '{0}' with the id '{1}'. "
                                        "Import of third party packages failed."
                                        .format(processor_config.module_name, processor_config.id))
        except Exception as e:
            logger.critical("{0}".format(str(e)), exc_info=config.EXC_INFO)
            success = False
        finally:
            return True if False not in success else False

    def _create_input_modules(self) -> bool:
        """
        Instantiate and connect all input modules.

        :returns: Boolean indicating if every module start-up was successful.
        """
        success = []
        try:
            input_configs = [input_config for input_config in self._configuration if
                             input_config.module_name.startswith("inputs.") and
                             not input_config.module_name.endswith(".variable") and
                             not input_config.module_name.endswith(".tag")]
            for input_config in input_configs:
                # Check if this module is already instantiated.
                if input_config.id not in data_layer.module_data:
                    # Get the according module.
                    input_module = data_layer.registered_modules.get(input_config.module_name)
                    self._check_if_deprecated(input_module)
                    try:
                        input_instance = input_module(configuration=input_config)
                        # Create an entry in the data layer.
                        data_layer.module_data[input_config.id] = models.ModuleData(
                            instance=input_instance,
                            configuration=input_config,
                            module_name=input_config.module_name)
                        if input_config.active:
                            if not input_instance.start():
                                success.append(False)
                                logger.critical("Could not start input module '{0}' with the id '{1}'. "
                                                "Initial connection was not successful. "
                                                "Please check the configuration."
                                                .format(input_config.module_name, input_config.id))
                                if bool(int(os.environ.get('IGNORE_START_FAIL', '0'))):
                                    self.retries.append(
                                        utils.retrying.RetryStart(module=data_layer.module_data[input_config.id]))
                            else:
                                logger.debug("Successfully started input module '{0}' with the id '{1}'."
                                             .format(input_config.module_name, input_config.id))
                    except ImportError:
                        success.append(False)
                        logger.critical("Could not start input module '{0}' with the id '{1}'. "
                                        "Import of third party packages failed."
                                        .format(input_config.module_name, input_config.id))
        except Exception as e:
            logger.critical("{0}".format(str(e)), exc_info=config.EXC_INFO)
            success = False
        finally:
            return True if False not in success else False

    def _create_tag_modules(self) -> bool:
        """
        Instantiate and connect all tag modules.

        :returns: Boolean indicating if every module start-up was successful.
        """
        success = []
        try:
            tag_configs = [tag_config for tag_config in self._configuration if
                           tag_config.module_name.endswith(".tag") and
                           tag_config.module_name.startswith("inputs.") and
                           not tag_config.module_name.endswith(".variable")]
            for tag_config in tag_configs:
                # Check if this module is already instantiated.
                if tag_config.id not in data_layer.module_data:
                    # Get the according module.
                    tag_module = data_layer.registered_modules.get(tag_config.module_name)
                    self._check_if_deprecated(tag_module)
                    try:
                        # Get the according input module if required.
                        input_module_instance = getattr(
                            data_layer.module_data.get(getattr(tag_config, "input_module", ""), None),
                            "instance", None)
                        tag_instance = tag_module(configuration=tag_config,
                                                  input_module_instance=input_module_instance)
                        # Create an entry in the data layer.
                        data_layer.module_data[tag_config.id] = models.ModuleData(
                            instance=tag_instance,
                            configuration=tag_config,
                            module_name=tag_config.module_name)
                        if tag_config.active:
                            if not tag_instance.start():
                                success.append(False)
                                logger.critical("Could not start tag module '{0}' with the id '{1}'. "
                                                "Initial connection was not successful. "
                                                "Please check the configuration."
                                                .format(tag_config.module_name, tag_config.id))
                                if bool(int(os.environ.get('IGNORE_START_FAIL', '0'))):
                                    self.retries.append(
                                        utils.retrying.RetryStart(module=data_layer.module_data[tag_config.id]))
                            else:
                                logger.debug("Successfully started processor module '{0}' with the id '{1}'."
                                             .format(tag_config.module_name, tag_config.id))
                    except ImportError:
                        success.append(False)
                        logger.critical("Could not instantiate tag module '{0}' with the id '{1}'. "
                                        "Import of third party packages failed."
                                        .format(tag_config.module_name, tag_config.id))
        except Exception as e:
            logger.critical("{0}".format(str(e)), exc_info=config.EXC_INFO)
            success = False
        finally:
            return True if False not in success else False

    def _create_variable_modules(self) -> bool:
        """
        Instantiate and connect all variable modules.

        :returns: Boolean indicating if every module start-up was successful.
        """
        success = []
        try:
            variable_configs = [variable_config for variable_config in self._configuration if
                                variable_config.module_name.endswith(".variable") and
                                variable_config.module_name.startswith("inputs.") and
                                not variable_config.module_name.endswith(".tag")]
            for variable_config in sorted(variable_configs, key=lambda variable_config: variable_config.start_priority,
                                          reverse=True):
                # Check if this module is already instantiated.
                if variable_config.id not in data_layer.module_data:
                    # Get the according module.
                    variable_module = data_layer.registered_modules.get(variable_config.module_name)
                    self._check_if_deprecated(variable_module)
                    try:
                        # Get the according input module if required.
                        input_module_instance = getattr(
                            data_layer.module_data.get(getattr(variable_config, "input_module", ""), None),
                            "instance", None)
                        variable_instance = variable_module(configuration=variable_config,
                                                            input_module_instance=input_module_instance)
                        # Create an entry in the data layer.
                        data_layer.module_data[variable_config.id] = models.ModuleData(
                            instance=variable_instance,
                            configuration=variable_config,
                            module_name=variable_config.module_name)
                        if variable_config.active:
                            if not variable_instance.start():
                                success.append(False)
                                logger.critical("Could not start variable module '{0}' with the id '{1}'. "
                                                "Initial connection was not successful. "
                                                "Please check the configuration."
                                                .format(variable_config.module_name, variable_config.id))
                                if bool(int(os.environ.get('IGNORE_START_FAIL', '0'))):
                                    self.retries.append(
                                        utils.retrying.RetryStart(module=data_layer.module_data[variable_config.id]))
                            else:
                                logger.debug("Successfully started variable module '{0}' with the id '{1}'."
                                             .format(variable_config.module_name, variable_config.id))
                    except ImportError:
                        success.append(False)
                        logger.critical("Could not start variable module '{0}' with the id '{1}'. "
                                        "Import of third party packages failed."
                                        .format(variable_config.module_name, variable_config.id))
        except Exception as e:
            logger.critical("{0}".format(str(e)), exc_info=config.EXC_INFO)
            success = False
        finally:
            return True if False not in success else False

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
                        stream.write(f'{yaml.dump(configuration_dict)}')
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
