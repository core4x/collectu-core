"""
Gets executed at start-up and sets all (default) environment variables given in the config file.
Furthermore, all defined third party requirements are checked and installed.
"""
from configparser import ConfigParser
import os
import logging
import uuid
import importlib.metadata

# Internal imports.
import config
import data_layer
import utils.plugin_interface

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def check_installed_app_packages():
    """
    Compares the installed app packages with the ones listed in the requirements.txt file.
    If a package is missing, an exception is raised. If a version differs, a critical log message is printed.
    """
    # Get all installed packages.
    installed_packages = {pkg.metadata['Name']: pkg.version for pkg in importlib.metadata.distributions()}

    # Get all required packages from requirements.txt.
    required_packages = {}
    with open("requirements.txt", "r") as requirements_file:
        for line in requirements_file.read().splitlines():
            if "==" in line:
                package_name, version = line.split("==", 1)
                required_packages[package_name] = version

    # Compare the installed and required packages.
    not_installed_required_packages = set(required_packages.items()) - set(installed_packages.items())
    if not_installed_required_packages:
        # Check if the package is missing, or installed in another version.
        for missing_package in not_installed_required_packages:
            if next(iter(missing_package)) not in installed_packages.keys():
                logger.critical("Missing package installation: {0}=={1}. Trying to install missing package..."
                                .format(missing_package[0], missing_package[1]))
                utils.plugin_interface.install_plugin_requirement(
                    package=missing_package[0] + "==" + missing_package[1])
            else:
                logger.error("Package version differs from the one defined in requirements.txt: {0}=={1}. "
                             "Trying to install required package..."
                             .format(missing_package[0], missing_package[1]))
                utils.plugin_interface.install_plugin_requirement(
                    package=missing_package[0] + "==" + missing_package[1])


def load_and_process_settings_file() -> bool:
    """
    Load the ini file and set the environment variables (if not already defined by e.g. docker-compose).

    :return: True if the settings file was updated, false otherwise.
    """
    try:
        parser = ConfigParser(comment_prefixes='/', allow_no_value=True)
        parser.read_file(open("../" + config.SETTINGS_FILENAME))

        updated: bool = False
        """Indicates if the config was updated e.g. when auto-generating an app_id."""

        # Set the environment variables if not already defined.
        for name, value in parser.items('env'):
            # If no app_id is set, we generate one.
            if name.lower() == "app_id":
                if not bool(value.strip()):
                    logger.info(f"Welcome to {config.APP_NAME}.")
                    value = str(uuid.uuid4())
                    parser.set('env', 'app_id', value)
                    updated = True
                    logger.info(f"Auto-generated app_id: '{value}'.")
                os.environ["APP_ID"] = value
                data_layer.settings[name.upper()] = str(value)
            elif not os.environ.get(name.upper(), False) and not name.startswith("#") and bool(value.strip()):
                logger.debug(f"Set environment variable from {config.SETTINGS_FILENAME}: {name.upper()}={value}")
                os.environ[name.upper()] = str(value)
                data_layer.settings[name.upper()] = str(value)
            elif os.environ.get(name.upper(), False):
                # Already set environment variables.
                data_layer.settings[name.upper()] = os.environ.get(name.upper())
            elif not name.startswith("#"):
                data_layer.settings[name.upper()] = str(value)

        # Write updated settings.ini file.
        if updated:
            parser.write(open("../" + config.SETTINGS_FILENAME, 'w'))  # Caution: everything is automatically lowered...

        logger.info(f"Successfully initialized app using {config.SETTINGS_FILENAME}.")
        return updated
    except Exception as e:
        logger.error("Could not initialize application: {0}".format(str(e)))


def update_env_variables():
    """
    Sets the environment variables and the settings.ini to the current values in data_layer.settings.
    """
    try:
        parser = ConfigParser(comment_prefixes='/', allow_no_value=True)
        parser.read_file(open("../" + config.SETTINGS_FILENAME))

        for key, value in data_layer.settings.items():
            os.environ[key] = value
            parser.set('env', key.lower(), value)

        parser.write(open("../" + config.SETTINGS_FILENAME, 'w'))  # Caution: everything is automatically lowered...
        logger.info(f"Successfully updated environment variables and {config.SETTINGS_FILENAME}.")
    except Exception as e:
        logger.error("Could not update and write settings: {0}".format(str(e)))
