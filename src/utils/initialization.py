"""
Gets executed at start-up and sets all (default) environment variables given in the config file.
Furthermore, all defined third party requirements are checked and installed.
"""
from configparser import ConfigParser
import os
import logging
import uuid
import socket
import importlib.metadata

# Internal imports.
import config
import data_layer
import utils.plugin_interface

# Third party imports.
# requests is imported below in order to be able to install third-party requirements on start-up.

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

    # If we have an interface module, we check those requirements as well.
    if os.path.exists("interface/requirements.txt"):
        with open("interface/requirements.txt", "r") as requirements_file:
            for line in requirements_file.read().splitlines():
                if "==" in line:
                    package_name, version = line.split("==", 1)
                    required_packages[package_name] = version

    # The main requirements (overwrite the one of the interface).
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
            if name.lower() == "app_id" and not os.environ.get(name.upper(), False):
                if not bool(value.strip()):
                    logger.info(f"Welcome to {config.APP_NAME}.")
                    value = str(uuid.uuid4())
                    parser.set('env', name.lower(), value)
                    updated = True
                    logger.info(f"Auto-generated app_id: '{value}'.")
                os.environ[name.upper()] = value
                data_layer.settings[name.upper()] = str(value)
            # If no app_description is set, we generate one.
            elif name.lower() == "app_description" and not os.environ.get(name.upper(), False):
                if not bool(value.strip()):
                    value = socket.gethostname()
                    parser.set('env', name.lower(), value)
                    logger.info(f"Auto-generated app_description: '{value}'.")
                os.environ[name.upper()] = value
                data_layer.settings[name.upper()] = str(value)
            # Set in settings but not in env.
            elif not os.environ.get(name.upper(), False) and not name.startswith("#") and bool(value.strip()):
                os.environ[name.upper()] = str(value)
                data_layer.settings[name.upper()] = str(value)
            # Set in env.
            elif os.environ.get(name.upper(), False):
                # Already set environment variables.
                data_layer.settings[name.upper()] = os.environ.get(name.upper())

        # Load the api_access_token.txt file if it exists.
        api_access_token_path = '../api_access_token.txt'
        try:
            if os.path.exists(api_access_token_path):
                with open(api_access_token_path, 'r') as file:
                    if os.environ.get("HUB_API_ACCESS_TOKEN", False):
                        logger.warning("Existing HUB_API_ACCESS_TOKEN is overwritten by {0}"
                                       .format(api_access_token_path))
                    os.environ["HUB_API_ACCESS_TOKEN"] = file.read().strip()
                    logger.info("Read HUB_API_ACCESS_TOKEN from file ({0}).".format(api_access_token_path))
            else:
                if not os.environ.get("HUB_API_ACCESS_TOKEN", False):
                    logger.warning("API access token file 'api_access_token.txt' does not exist...")
        except Exception as e:
            logger.error("Something went wrong loading API access token: {0}".format(str(e)), exc_info=config.EXC_INFO)

        if os.environ.get("HUB_API_ACCESS_TOKEN", False):
            # Third party imports.
            import requests

            session = requests.Session()
            session.headers = {"Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"}
            try:
                response = session.post(url=config.HUB_TEST_TOKEN_ADDRESS, timeout=(5, 5))
                response.raise_for_status()
                username = response.json().get("username")
                logger.info("Your authentication token belongs to {0}.".format(username))
                os.environ["HUB_USERNAME"] = username
            except Exception as e:
                logger.error("Could not get your current username. "
                             "Authentication with hub '{0}' failed. You may be using an invalid api access token: {1}. "
                             "Please check or create an api access token on your hub profile."
                             .format(config.HUB_TEST_TOKEN_ADDRESS, str(e)), exc_info=config.EXC_INFO)

        # Write updated settings.ini file.
        if updated:
            parser.write(open("../" + config.SETTINGS_FILENAME, 'w'))  # Caution: everything is automatically lowered...

        logger.info(f"Successfully initialized app using {config.SETTINGS_FILENAME}.")
        return updated
    except Exception as e:
        logger.error("Could not initialize application: {0}".format(str(e)))
        return False


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
