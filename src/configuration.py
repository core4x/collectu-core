"""
The configuration class.
"""
from datetime import datetime, timezone
import os
import sys
import copy
import logging
import time
import pathlib
import traceback
import uuid
import asyncio
import inspect
import threading
from collections import defaultdict
from typing import Any, Union, Optional
from pprint import pformat
import queue
import dataclasses

# Internal imports.
import utils.config_store
import utils.secrets
import config
import data_layer
import models
from models.validations import ValidationError
from metrics import metrics_registry
import utils.hub_connection

# Third party imports.
import json

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)

CONFIGURATION_DIR = pathlib.Path('..', 'configuration')
"""The one directory configuration files are read from and written to."""

# Third-party imports (optional).
try:
    import yaml
except ImportError as e:
    yaml = None
    logger.error("Optional yaml package not installed! Some features may not be supported.")


def configuration_path(filename: str) -> pathlib.Path:
    """
    Resolve a configuration filename to a path inside the configuration directory.

    A subdirectory *within* the configuration folder stays allowed — `save` creates the
    parents, so `line_3/press.yml` is an ordinary thing to ask for. What is refused is
    anything that resolves outside it.

    :param filename: The filename, possibly with subdirectories, to resolve.

    :returns: The absolute path to the file.

    :raises ValueError: If the filename resolves outside the configuration directory.
    """
    root = CONFIGURATION_DIR.resolve()
    # `resolve()` on both sides, so the comparison is between two absolute, normalised
    # paths — `..` already collapsed, symlinks already followed, and on Windows the
    # drive letter and separators already agreed.
    path = (root / filename).resolve()

    if path != root and root not in path.parents:
        raise ValueError("The configuration filename '{0}' is outside the configuration directory."
                         .format(filename))
    if path == root:
        raise ValueError("'{0}' is the configuration directory, not a file.".format(filename))

    return path

_thread_local = threading.local()
"""
Thread-local storage for persistent async event loops.

Each thread that calls _invoke with an async method gets its own event loop created
on first use and reused for all subsequent calls on that thread. This avoids the
overhead of creating and tearing down a new event loop on every call.

The loop is stored under _thread_local.event_loop and is never shared between threads.
"""


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
        self.config_db = utils.config_store.open_store(
            os.path.join('..', 'data', 'configuration', 'configuration.db'),
            description="the configuration library")
        """
        The configuration library.

        Saved configurations and autosaves — history, not the running pipeline, which
        is loaded from a file in /configuration and does not come from here. So when
        tinydb is missing this is an in-memory store rather than nothing: saving,
        opening and autosaving all work for as long as the app runs, and only the
        history across a restart is lost. `config_db.persistent` says which it is.
        """
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

    @staticmethod
    def _invoke(method, *args, **kwargs):
        """
        Calls a method while transparently supporting both synchronous and asynchronous implementations.

        Synchronous methods are called directly with no overhead. For asynchronous
        methods, one of two execution strategies is chosen based on whether an event
        loop is already running on the current thread:

          - No running loop: a persistent event loop is reused for the lifetime of
            the calling thread via a thread-local variable. This avoids the cost of
            creating and tearing down a new event loop on every call.
          - Running loop detected: to avoid a 'This event loop is already running'
            deadlock, the coroutine is dispatched to a dedicated daemon thread that
            owns its own event loop via asyncio.run(). The calling thread blocks on
            join() until the call completes.

        Used to invoke start() and stop() on module instances, both of which may be
        implemented as either regular or async methods.

        :param method: The bound method to invoke.
        :param args: Positional arguments forwarded to the method.
        :param kwargs: Keyword arguments forwarded to the method.
        :returns: The return value of the method, if any.
        :raises Exception: Re-raises any exception thrown inside an async method dispatched to a worker thread.
        """
        if not inspect.iscoroutinefunction(method):
            return method(*args, **kwargs)

        try:
            asyncio.get_running_loop()
            # A loop is running on this thread — dispatch to a separate thread to avoid a deadlock.
            result, exc = [None], [None]

            def _run_in_thread():
                try:
                    result[0] = asyncio.run(method(*args, **kwargs))
                except Exception as e:
                    exc[0] = e

            t = threading.Thread(target=_run_in_thread, daemon=True)
            t.start()
            # Deliberately without a timeout. This also carries the start method of a module, which
            # legitimately runs for the lifetime of that module, and returning early would let
            # _start_module call start a second time. An async stop which never returns is caught
            # one level up, by the bounded wait in stop and stop_module, and reported there.
            t.join()
            if exc[0]:
                raise exc[0]
            return result[0]

        except RuntimeError:
            # No running loop — reuse a persistent thread-local event loop.
            loop = getattr(_thread_local, "event_loop", None)
            if loop is None or loop.is_closed():
                loop = asyncio.new_event_loop()
                _thread_local.event_loop = loop
            return loop.run_until_complete(method(*args, **kwargs))

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
                    self.config_db.insert(entry)
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

                    updates = self.config_db.update(update_dict, 'id', config_id)
                    if updates > 0:
                        logger.debug("Updated entry with the id '{0}' in configuration database.".format(config_id))
                    else:
                        logger.warning("Could not update entry in configuration database. "
                                       "Could not find entry with the id '{0}'.".format(config_id))
                elif task == "delete":
                    removals = self.config_db.remove('id', config_id)
                    if removals > 0:
                        logger.debug("Removed entry with the id '{0}' from configuration database."
                                     .format(config_id))
                    else:
                        logger.warning("Could not remove entry in configuration database. "
                                       "Could not find entry with the id '{0}'.".format(config_id))
                elif task is not None:
                    logger.error("Unknown task in database query: {0}".format(task))

                # Check the number of autosave elements (config.AUTOSAVE_NUMBER) and remove the oldest ones,
                # if we have more.
                while len(self.config_db.search('autosave', True)) > config.AUTOSAVE_NUMBER:
                    oldest_element = min(self.config_db.search('autosave', True),
                                         key=lambda x: x['updated_at'])
                    self.config_db.remove('id', oldest_element.get("id"))
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
            entry = self.config_db.get('id', config_id)
            if entry is not None and convert_timestamps:
                entry["created_at"] = datetime.fromisoformat(entry["created_at"])
                entry["updated_at"] = datetime.fromisoformat(entry["updated_at"])
            return entry
        else:
            entries = self.config_db.all()
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
            # Set the path to the file, guaranteed to be inside the configuration directory — see `configuration_path`.
            file = configuration_path(filename)
            # Read the file.
            with open(file) as content:
                content = content.read().strip()
            logger.info(f'Loading configuration from {filename}.')
            # Load the configuration file defined in the environment variable.
            errors = self.load_configuration_from_stream(content=content)
        except Exception as e:
            errors = {"-": ["Failed to load configuration file '{0}': {1}".format(filename, str(e))]}
        return errors

    def load_configuration_from_stream(self, content: str) -> dict[str, list[str]]:
        """
        Deserializes the given stream using the configuration model.
        Possible validation errors are included in the returned error dictionary.
        The deserialized configuration will be automatically executed if no errors occurred.

        :param content: The content of the configuration as yaml or json.

        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
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

                # logger.debug("Deserialized configuration:\n" + pformat(configuration))
                logger.info("Successfully set new configuration.")
        except Exception as e:
            errors = {"-": ["Failed to process configuration stream: {0}".format(str(e))]}
        return errors

    @staticmethod
    def deserialize_config(cls, data: dict):
        """
        Deserializes the given data using the dataclass model.

        :param cls: The dataclass to use for deserialization.
        :param data: The data to deserialize.
        :return: The deserialized data.
        """
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        unknown = set(data) - valid_keys
        for key in unknown:
            logger.warning(f"Unknown key '{key}' in configuration for module '{data.get('id', '-')}' - ignoring.")
        return cls(**{k: v for k, v in data.items() if k in valid_keys})

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

            # A configuration downloaded from the hub carries a placeholder wherever the hub
            # removed a secret before publishing it. The credential is simply not there, so it is
            # reported here rather than at connect time, where it surfaces as a failed login.
            for module_id, key in utils.secrets.placeholders(configuration_dict):
                errors[module_id].append("The parameter '{0}' holds no value. It was removed by "
                                         "the hub because it is secret. Please enter "
                                         "the value, or supply it at runtime with a dynamic variable "
                                         "such as ${{env.MY_PASSWORD}}.".format(key))

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
                        configuration.append(Configuration.deserialize_config(module_schema, module_configuration))
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
        # Make a 'normal' dict from the defaultdict().
        errors = dict(errors.items())
        return configuration, configuration_dict, errors

    def _start(self):
        """
        Start the execution of the current configuration.
        Only modules which are not currently running are started.
        """
        logger.info("Starting configuration start routine...")
        self._create_buffer_module()
        self._create_output_modules()
        self._create_processor_modules()
        self._create_input_modules()
        self._create_tag_modules()
        self._create_variable_modules()
        logger.info("Finished configuration start routine ({0} module(s) running)."
                    .format(len(self.configuration_dict)))

    def restart(self):
        """
        Restart the current configuration.
        The module_data and metrics are reset.
        """
        self.stop()
        metrics_registry.reset()
        self._start()

    def start_module(self, module_id: str = None, module_config: dict = None) -> dict[str, list[str]]:
        """
        Start a module. Behavior depends on what is provided:

        - Only module_id: The module must already exist and will be restarted with its current config.
        - Only module_config: The id is extracted from module_config. If the module exists, it is
          updated with the new config and restarted. Otherwise, it is freshly started.
        - Both module_id and module_config: The module_id takes precedence as the identifier.
          If the module exists, it is updated with the new config and restarted.
          Otherwise, it is freshly started.

        :param module_id: The id of the module to start.
        :param module_config: The module configuration as a dict.
        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        try:
            if module_id is None and module_config is None:
                return {"-": ["Either module_id or module_config must be provided."]}

            if module_id is None:
                # Derive module_id from module_config.
                module_id = module_config.get("id")
                if module_id is None:
                    return {"-": ["module_config must contain an 'id' field."]}
            elif module_config is not None:
                # Ensure the id in the config is consistent with the given module_id.
                module_config["id"] = module_id

            if module_id in data_layer.module_data:
                module_data = data_layer.module_data[module_id]

                if module_config is not None:
                    # Validate the new module config in the context of the full configuration,
                    # replacing the old entry for this module_id.
                    candidate_dict = [m for m in self._configuration_dict if m.get("id") != module_id]
                    candidate_dict += [module_config]
                else:
                    # No new config — reuse the existing config dict as-is.
                    candidate_dict = self._configuration_dict

                configuration, configuration_dict, errors = self.validate_configuration_from_stream(
                    json.dumps(candidate_dict, default=lambda o: o.__dict__))
                if errors:
                    return errors

                # Stop the running instance and wait for it to finish.
                t = threading.Thread(target=self._stop_module, args=(module_data,), daemon=True,
                                     name="Stop_{0}".format(module_id))
                t.start()
                # Bounded, so a module whose stop routine never returns can not block this call,
                # and with it the request which triggered it, forever.
                t.join(timeout=config.STOP_TIMEOUT)
                if t.is_alive():
                    logger.error("The stop routine of module '{0}' with the id '{1}' did not return within {2} s."
                                 .format(module_data.module_name, module_id, config.STOP_TIMEOUT))
                    self._report_leaked_threads(module_ids=[module_id], timeout=config.STOP_TIMEOUT)

                if module_config is not None:
                    # Remove the old instance from the data layer.
                    if getattr(module_data.configuration, "is_buffer", False):
                        data_layer.buffer_instance = None
                    data_layer.module_data.pop(module_id)
                    for dashboard_module in data_layer.dashboard_modules:
                        if dashboard_module.configuration.id == module_id:
                            data_layer.dashboard_modules.remove(dashboard_module)

                # Update the stored configuration.
                self._configuration = configuration
                self._configuration_dict = configuration_dict

                # Extract the validated config object for this module and create it.
                module_configuration = next((m for m in configuration if m.id == module_id), None)
                if module_configuration is None:
                    return {module_id: ["Could not find validated configuration for module '{0}'.".format(module_id)]}

                if module_config is not None:
                    self._create_module(module_config=module_configuration)
                else:
                    # No new config — restart the existing instance by re-activating it.
                    # The previous start loop runs against this very instance and leaves it only
                    # because active is false. Re-activating while it is still running - a module
                    # sleeping off a long interval, or one blocked in a call that does not return -
                    # would give the module two loops instead of one, so it is refused instead.
                    running = [thread.name for thread in self._alive_module_threads([module_id])
                               if thread.name.startswith("Start_")]
                    if running:
                        logger.error("Could not restart module '{0}' with the id '{1}': its previous start routine "
                                     "is still running ({2}). Restarting now would run the module twice. "
                                     "Please try again once it has ended."
                                     .format(module_data.module_name, module_id, ", ".join(running)))
                        self._report_leaked_threads(module_ids=[module_id], timeout=config.STOP_TIMEOUT)
                        return {module_id: ["The previous start routine of the module is still running. "
                                            "Please try again."]}
                    module_data.instance.active = True
                    t = threading.Thread(target=self._start_module, args=(module_data,), daemon=True,
                                         name="Start_{0}".format(module_id))
                    t.start()

            else:
                # Module does not exist yet — module_config is required.
                if module_config is None:
                    return {module_id: ["Module '{0}' does not exist. Please provide a module_config to start it."
                                        .format(module_id)]}
                logger.info("Module '{0}' does not exist yet. Starting fresh.".format(module_id))
                errors = self.add_modules_to_configuration(
                    content=json.dumps([module_config], default=lambda o: o.__dict__))
                if errors:
                    return errors

            logger.info("Successfully started module '{0}' with the id '{1}'."
                        .format(data_layer.module_data[module_id].module_name,
                                data_layer.module_data[module_id].configuration.id))
            return {}

        except Exception as e:
            logger.error("Unexpected error while trying to start module '{0}': {1}".format(module_id, str(e)),
                         exc_info=config.EXC_INFO)
            return {module_id or "-": ["Unexpected error while trying to start module: {0}".format(str(e))]}

    def stop_module(self, module_id: str) -> dict[str, list[str]]:
        """
        Stop a running module by its id without removing it from the configuration.
        The module can be restarted later with start_module(module_id=...).
        If the module does not exist, a warning is logged and an empty dict is returned.

        :param module_id: The id of the module to stop.
        :returns: A dict of error messages with the module id (if it exists, otherwise '-') as key.
        """
        try:
            if module_id not in data_layer.module_data:
                logger.warning("Could not stop module '{0}': module does not exist.".format(module_id))
                return {}

            module_data = data_layer.module_data[module_id]
            logger.debug("Trying to stop module '{0}' with the id '{1}'."
                         .format(module_data.module_name, module_data.configuration.id))
            t = threading.Thread(target=self._stop_module,
                                 args=(module_data,),
                                 daemon=True,
                                 name="Stop_{0}".format(module_id))
            t.start()
            t.join(timeout=config.STOP_TIMEOUT)
            if t.is_alive():
                logger.error("Could not stop module '{0}' with id '{1}'."
                             .format(module_data.module_name, str(module_data.configuration.id)))
                self._report_leaked_threads(module_ids=[module_id], timeout=config.STOP_TIMEOUT)
                return {module_id: ["Could not stop module within time."]}
            else:
                logger.info("Successfully stopped module '{0}' with the id '{1}'."
                            .format(module_data.module_name, str(module_data.configuration.id)))
                # The stop routine returned, but the start loop of the module may still be running.
                self._report_leaked_threads(module_ids=[module_id], timeout=config.STOP_TIMEOUT)
            return {}
        except Exception as e:
            logger.error("Unexpected error while trying to stop module '{0}': {1}".format(module_id, str(e)),
                         exc_info=config.EXC_INFO)
            return {module_id: ["Unexpected error while trying to stop module: {0}".format(str(e))]}

    @staticmethod
    def _stop_module(module_data):
        """
        Calls the stop method of a given module instance, supporting both synchronous
        and asynchronous stop implementations.

        Sets active to False before calling stop so the module's internal loops exit
        cleanly regardless of how stop is implemented. Should be called in a separate
        thread, as it blocks until stop completes.

        :param module_data: The module data containing the instance to stop.
        """
        try:
            logger.debug("Trying to stop module '{0}' with the id '{1}'."
                         .format(module_data.module_name, module_data.configuration.id))
            module_data.instance.active = False
            # The module is no longer ready to process data - its stop routine releases
            # exactly the resources the readiness flag stands for.
            module_data.instance.started.clear()
            Configuration._invoke(module_data.instance.stop)
        except Exception as e:
            logger.error("Could not stop module '{0}' with the id '{1}': {2}"
                         .format(module_data.module_name, module_data.configuration.id,
                                 str(e)), exc_info=config.EXC_INFO)

    @staticmethod
    def _spawn_stop_threads(modules: dict[str, "models.ModuleData"]) -> list[tuple[str, threading.Thread]]:
        """
        Start one daemon thread per given module, each calling the stop routine of the module.

        The threads are named 'Stop_<module id>', so a thread which outlives the stop routine
        can be traced back to the module it belongs to. See _report_leaked_threads.

        :param modules: The modules to stop, with the module id as key.
        :returns: A list of tuples, each with the module id and the started thread.
        """
        sorted_modules = dict(sorted(modules.items(), key=lambda item: item[1].configuration.start_priority))
        threads = [(module_id, threading.Thread(target=Configuration._stop_module,
                                                args=(module_data,),
                                                daemon=True,
                                                name="Stop_{0}".format(module_id)))
                   for module_id, module_data in sorted_modules.items()]
        for _, t in threads:
            t.start()
        return threads

    @staticmethod
    def _alive_module_threads(module_ids: list[str]) -> list[threading.Thread]:
        """
        Collect all running threads which belong to one of the given modules.

        Threads are matched by the naming convention used when they are created:
        'Start_<id>', 'Stop_<id>' and 'Link_<id>_to_<id of the linked module>'.

        :param module_ids: The ids of the modules whose threads are searched.
        :returns: The threads which are still alive.
        """
        prefixes = tuple(prefix.format(module_id)
                         for module_id in module_ids
                         for prefix in ("Start_{0}", "Stop_{0}", "Link_{0}_to_"))
        if not prefixes:
            return []
        return [thread for thread in threading.enumerate() if (thread.name or "").startswith(prefixes)]

    @staticmethod
    def _report_leaked_threads(module_ids: list[str], timeout: float) -> list[str]:
        """
        Log every thread which still belongs to one of the given modules after they were stopped.

        Python can not kill a thread. A module which ignores self.active, or which is blocked in
        a call that never returns, therefore keeps its thread alive for as long as the process
        runs. All threads of the app are daemon threads, so they can never block a shutdown, and
        _call_links drops everything a leaked thread produces, so it can not feed data into a
        configuration it no longer belongs to. What is left to do is to say precisely which thread
        refused to end and where it is stuck, which is the information needed to fix the module.

        The stack of a leaked thread is only logged if config.EXC_INFO is set, following the same
        convention as the traceback of an exception.

        :param module_ids: The ids of the modules which were asked to stop.
        :param timeout: The exceeded stop timeout in seconds, used for the log message.
        :returns: The names of the threads which are still alive.
        """
        threads = Configuration._alive_module_threads(module_ids)
        if not threads:
            return []

        # A private but long-stable interface. It is the only way to see where a foreign thread
        # currently is, and a stop routine must never fail because of a diagnostic message.
        try:
            frames = sys._current_frames()
        except Exception:
            frames = {}

        leaked = []
        for thread in threads:
            name = thread.name or ""
            leaked.append(name)
            location = ""
            if config.EXC_INFO:
                frame = frames.get(thread.ident)
                if frame is not None:
                    location = " It is currently at:\n{0}".format("".join(traceback.format_stack(frame)).rstrip())
            logger.warning("Thread '{0}' did not end within {1} s and is leaked. It can not be killed and keeps "
                           "holding whatever it is blocked on until the app is restarted.{2}"
                           .format(name, timeout, location))

        if leaked and not config.EXC_INFO:
            logger.warning("Set the environment variable EXC_INFO to true to log where the leaked thread(s) "
                           "are currently blocked.")
        return leaked

    def stop(self):
        """
        Stop the execution of a configuration. Everything is reset.
        """
        try:
            logger.info("Starting configuration stop routine...")
            module_ids = list(data_layer.module_data.keys())

            # Stop all variable modules by setting self.active to false and calling the stop method.
            var_threads = self._spawn_stop_threads(
                {k: v for k, v in data_layer.module_data.items() if
                 v.module_name.endswith(".variable") and v.module_name.startswith("inputs.")})

            # Now, no new data should be generated.
            # Wait a little, until all pipelines have executed.
            # However, this does not guarantee all pipelines finished.
            # In case a pipeline hasn't finished, an error message is (probably) generated.
            time.sleep(0.5)

            # Stop all tag modules.
            tag_threads = self._spawn_stop_threads(
                {k: v for k, v in data_layer.module_data.items() if
                 v.module_name.endswith(".tag") and v.module_name.startswith("inputs.")})

            # Stop all input modules.
            in_threads = self._spawn_stop_threads(
                {k: v for k, v in data_layer.module_data.items() if
                 v.module_name.startswith("inputs.") and not v.module_name.endswith(
                     ".variable") and not v.module_name.endswith(".tag")})

            # Stop all processor modules.
            pro_threads = self._spawn_stop_threads(
                {k: v for k, v in data_layer.module_data.items() if
                 v.module_name.startswith("processors.")})

            # Stop all output modules.
            out_threads = self._spawn_stop_threads(
                {k: v for k, v in data_layer.module_data.items() if
                 v.module_name.startswith("outputs.")})

            stop_threads = var_threads + tag_threads + in_threads + pro_threads + out_threads

            start_time = time.time()
            # Wait for the stopping threads to finish.
            while time.time() - start_time < config.STOP_TIMEOUT:
                if all(not t.is_alive() for _, t in stop_threads):
                    break
                time.sleep(0.1)

            unstopped = [module_id for module_id, t in stop_threads if t.is_alive()]
            if unstopped:
                logger.error("The stop routine of {0} of {1} module(s) did not return within {2} s: {3}."
                             .format(len(unstopped), len(stop_threads), config.STOP_TIMEOUT, ", ".join(unstopped)))

            # Report every thread which is still running, not just the ones whose stop routine hung.
            # A module whose stop returned cleanly can still have left its start loop behind.
            self._report_leaked_threads(module_ids=module_ids, timeout=config.STOP_TIMEOUT)

            logger.info("Successfully finished configuration stop routine (stopped {0} of {1} module(s))."
                        .format(len(stop_threads) - len(unstopped), len(module_ids)))
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
                                     daemon=True, name="Stop_{0}".format(module_id)).start()
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
    def _start_module(module_data: models.ModuleData):
        """
        Calls the start method of a given module instance, supporting both synchronous
        and asynchronous start implementations.

        Retries on failure using config.RETRY_INTERVAL until the module is no longer
        active. If start completes without raising an exception, the loop exits — the
        module is expected to handle its own internal error recovery after that point.
        Should be called in a separate thread, as it blocks for the lifetime of the
        module's start method.

        Tag and variable modules are not started before the input module they belong to
        reported that it is ready, since they normally use one of its resources.

        :param module_data: The module data containing the instance to start.
        """
        retries: int = 0
        # An instance can be restarted in place, so a readiness reported by a previous run
        # has to be dropped before the start method is called again.
        module_data.instance.started.clear()
        # Wait for the input module this module depends on (if any) to be ready.
        module_data.instance._await_input_module()
        while getattr(module_data.instance, "active", False):
            try:
                Configuration._invoke(module_data.instance.start)
            except Exception as e:
                # A start method which blocks for the lifetime of the module reports its
                # readiness itself. If it raises later on (e.g. the connection was lost),
                # that readiness no longer holds while the module is being retried.
                module_data.instance.started.clear()
                logger.error("Could not start module '{0}' with the id '{1}'. Retrying in {2} seconds: {3}"
                             .format(module_data.module_name, module_data.configuration.id,
                                     config.RETRY_INTERVAL, str(e)), exc_info=config.EXC_INFO)
                time.sleep(config.RETRY_INTERVAL)
                retries += 1
                logger.error("Retrying to start module '{0}' with the id '{1}' in the {2} attempt."
                             .format(module_data.module_name, module_data.configuration.id, str(retries)))
            else:
                # The start method returned without raising, so the module is ready to process
                # data. Modules whose start method blocks for the lifetime of the module never
                # get here and report their readiness themselves.
                module_data.instance.started.set()
                if retries > 0:
                    logger.info("Successfully started module '{0}' with the id '{1}' after {2} retries."
                                .format(module_data.module_name, module_data.configuration.id, retries))
                else:
                    logger.debug("Successfully started module '{0}' with the id '{1}'."
                                 .format(module_data.module_name, module_data.configuration.id))
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
        if module_config.id in data_layer.module_data:
            logger.info("Module '{0}' already exists. Skipping starting procedure..."
                        .format(str(module_config.id)))
        else:
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

                threading.Thread(target=cls._start_module,
                                     args=(data_layer.module_data[module_config.id],),
                                     daemon=True,
                                     name="Start_{0}".format(module_config.id)).start()
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
        All outputs are created in parallel; the method blocks until every
        instantiation thread has completed before returning.
        """
        output_configs = [output_config for output_config in self._configuration if
                          not getattr(output_config, "is_buffer", False)
                          and output_config.module_name.startswith("outputs.")]

        for output_config in sorted(output_configs,
                                    key=lambda output_config: output_config.start_priority,
                                    reverse=True):
            self._create_module(output_config)

    def _create_processor_modules(self):
        """
        Create all processor modules.
        All processors are created in parallel; the method blocks until every
        instantiation thread has completed before returning.
        """
        processor_configs = [processor_config for processor_config in self._configuration if
                             processor_config.module_name.startswith("processors.")]

        for processor_config in sorted(processor_configs,
                                       key=lambda processor_config: processor_config.start_priority,
                                       reverse=True):
            self._create_module(processor_config)

    def _create_input_modules(self):
        """
        Instantiate and connect all input modules.
        All inputs are created in parallel; the method blocks until every
        instantiation thread has completed before returning.
        """
        input_configs = [input_config for input_config in self._configuration if
                         input_config.module_name.startswith("inputs.") and
                         not input_config.module_name.endswith(".variable") and
                         not input_config.module_name.endswith(".tag")]

        for input_config in sorted(input_configs,
                                   key=lambda input_config: input_config.start_priority,
                                   reverse=True):
            self._create_module(input_config)

    def _create_tag_modules(self):
        """
        Instantiate and connect all tag modules.
        All tags are created in parallel; the method blocks until every
        instantiation thread has completed before returning.
        """
        tag_configs = [tag_config for tag_config in self._configuration if
                       tag_config.module_name.endswith(".tag") and
                       tag_config.module_name.startswith("inputs.") and
                       not tag_config.module_name.endswith(".variable")]

        for tag_config in sorted(tag_configs,
                                 key=lambda tag_config: tag_config.start_priority,
                                 reverse=True):
            self._create_module(tag_config)

    def _create_variable_modules(self):
        """
        Instantiate and connect all variable modules.
        All variables are created in parallel; the method blocks until every
        instantiation thread has completed before returning.
        """
        variable_configs = [variable_config for variable_config in self._configuration if
                            variable_config.module_name.endswith(".variable") and
                            variable_config.module_name.startswith("inputs.") and
                            not variable_config.module_name.endswith(".tag")]

        for variable_config in sorted(variable_configs,
                                      key=lambda variable_config: variable_config.start_priority,
                                      reverse=True):
            self._create_module(variable_config)

    def save_configuration_as_file(self, filename: str | None = None, content: str | None = None) -> tuple[bool, str]:
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
            content = json.dumps(self._configuration_dict)

        # This is the file path including the file name, guaranteed to be inside the configuration directory.
        try:
            file = configuration_path(filename)
        except ValueError as e:
            return False, str(e)

        try:
            # Validate the content.
            configuration, configuration_dict, errors = self.validate_configuration_from_stream(content=content)
            if errors:
                return False, f"The given content is not a valid configuration."
            else:
                # Create directory and file.
                file.parent.mkdir(parents=True, exist_ok=True)
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
