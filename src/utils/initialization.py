"""
Gets executed at start-up and sets all (default) environment variables given in the config file.
Furthermore, all defined third party requirements are checked and installed.
"""
from configparser import ConfigParser
import os
import re
import logging
import uuid
import socket
import importlib.metadata
import secrets
import string
import base64

# Internal imports.
import config
import data_layer
import utils.plugin_interface

# Third party imports.
# requests is imported below in order to be able to install third-party requirements on start-up.

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def _normalize_package_name(name: str) -> str:
    """
    Normalize a distribution name for comparison, following PEP 503.

    'ruamel.yaml', 'ruamel-yaml' and 'Ruamel_YAML' all name the same distribution, but
    requirements.txt and the installed metadata do not have to spell it the same way. Compared
    verbatim, the difference read as a missing package and triggered a needless reinstall.

    :param name: The distribution name as written.
    :returns: The normalized name.
    """
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def _read_pinned_requirements(path: str, into: dict[str, tuple[str, str]]):
    """
    Read the '=='-pinned requirements of a requirements file into the given dict.

    :param path: The requirements file to read.
    :param into: The dict to fill, keyed by normalized name with (name as written, version).
    """
    with open(path, "r") as requirements_file:
        for line in requirements_file.read().splitlines():
            line = line.split("#", 1)[0].strip()
            if "==" in line:
                package_name, version = line.split("==", 1)
                package_name = package_name.strip()
                into[_normalize_package_name(package_name)] = (package_name, version.strip())


def check_installed_app_packages():
    """
    Compares the installed app packages with the ones listed in the requirements.txt file.
    If a package is missing, an exception is raised. If a version differs, a critical log message is printed.
    """
    # Get all installed packages.
    installed_packages = {_normalize_package_name(pkg.metadata['Name']): pkg.version
                          for pkg in importlib.metadata.distributions() if pkg.metadata['Name']}

    # Get all required packages from requirements.txt, keyed by normalized name.
    required_packages: dict[str, tuple[str, str]] = {}

    # If we have an interface module, we check those requirements as well.
    if os.path.exists("interface/requirements.txt"):
        # If MCP server is enabled.
        if bool(int(os.environ.get('MCP', '0'))):
            _read_pinned_requirements("interface/requirements-mcp.txt", required_packages)
        _read_pinned_requirements("interface/requirements.txt", required_packages)

    # The main requirements (overwrite the one of the interface).
    _read_pinned_requirements("requirements.txt", required_packages)

    auto_install = bool(int(os.environ.get('AUTO_INSTALL', '0')))

    # Compare the installed and required packages.
    for normalized_name, (package_name, version) in sorted(required_packages.items()):
        installed_version = installed_packages.get(normalized_name)
        if installed_version == version:
            continue

        required_package_str = f"{package_name}=={version}"
        if installed_version is None:
            if auto_install:
                logger.error("Missing package installation: {0}. Attempting to install..."
                             .format(required_package_str))
                utils.plugin_interface.install_plugin_requirement(package=required_package_str)
            else:
                logger.critical("Missing package installation: {0}. AUTO_INSTALL is disabled, skipping installation."
                                .format(required_package_str))
        else:
            logger.error("Package version {0} differs from the one defined in requirements.txt: {1}."
                         .format(installed_version, required_package_str))
            if auto_install:
                utils.plugin_interface.install_plugin_requirement(package=required_package_str)
            else:
                logger.critical("Wrong package version: {0}. AUTO_INSTALL is disabled, skipping upgrade."
                                .format(required_package_str))


def load_and_process_settings_file() -> bool:
    """
    Load the ini file and set the environment variables (if not already defined by e.g. docker-compose).

    :return: True if the settings file was updated, false otherwise.
    """
    try:
        settings_path = "../" + config.SETTINGS_FILENAME
        parser = ConfigParser(comment_prefixes='/', allow_no_value=True)
        with open(settings_path) as settings_file:
            parser.read_file(settings_file)

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
                    logger.info(f"Auto-generated app_id: {value}")
                os.environ[name.upper()] = value
                data_layer.settings[name.upper()] = str(value)
            elif name.lower() == "local_admin_password" and not os.environ.get(name.upper(), False):
                if not bool(value.strip()):
                    value = ''.join(secrets.choice(string.ascii_letters + string.digits + "!$&*+-<>?@_") for _ in range(16))
                    parser.set('env', name.lower(), value)
                    updated = True
                    # The value itself is deliberately not logged. Log records are mirrored into
                    # data_layer.latest_logs and reported to the hub and every configured
                    # mothership, which would put the admin password on the wire and into a
                    # remote log. It is written to the settings file just below.
                    logger.info("Auto-generated a local_admin_password. "
                                "You find it as 'local_admin_password' in your {0}."
                                .format(config.SETTINGS_FILENAME))
                os.environ[name.upper()] = value
                data_layer.settings[name.upper()] = str(value)
            # If no app_description is set, we generate one.
            elif name.lower() == "app_description" and not os.environ.get(name.upper(), False):
                if not bool(value.strip()):
                    value = socket.gethostname()
                    parser.set('env', name.lower(), value)
                    updated = True
                    logger.info(f"Auto-generated app_description: {value}")
                os.environ[name.upper()] = value
                data_layer.settings[name.upper()] = str(value)
            # Set in settings but not in env.
            elif not os.environ.get(name.upper(), False) and not name.startswith("#"):
                # We do not set empty hub_api_access_token values, as it would appear in frontend settings empty and overwrite existing ones if saved.
                if name.lower() == "hub_api_access_token" and not bool(value.strip()):
                    continue
                os.environ[name.upper()] = str(value)
                data_layer.settings[name.upper()] = str(value)
            # Set in env.
            elif os.environ.get(name.upper(), False):
                # Already set environment variables.
                data_layer.settings[name.upper()] = os.environ.get(name.upper())

        # Safe GIT_ACCESS_TOKEN (base64-encoded) as file.
        # Guarded on its own, so a malformed token cannot abort the rest of the initialization
        # below - the api access token in particular used to be skipped along with it.
        git_access_token = os.environ.get("GIT_ACCESS_TOKEN", False)
        if git_access_token:
            try:
                decoded_token = base64.b64decode(git_access_token).decode("utf-8")
                token_path = "../git_access_token.txt"
                with open(token_path, 'w') as file:
                    file.write(decoded_token)
                # The file is an ssh private key, and ssh refuses a key others can read.
                try:
                    os.chmod(token_path, 0o600)
                except OSError as e:
                    logger.warning("Could not restrict the permissions of {0}: {1}".format(token_path, str(e)))
                logger.info("Successfully updated git_access_token.txt file with your git token.")
            except Exception as e:
                logger.error("Could not store the GIT_ACCESS_TOKEN: {0}".format(str(e)), exc_info=config.EXC_INFO)

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

        if (os.environ.get("HUB_API_ACCESS_TOKEN", False) and
                os.environ.get("REPORT_TO_HUB", False) and
                not os.environ.get("HUB_USERNAME", False)):
            # Third party imports.
            try:
                import requests
                import utils.resilient_session
            except ImportError:
                logger.error("Could not get your current username. "
                                "Authentication with hub '{0}' failed. Requests package is not installed. Retrying later..."
                                .format(config.HUB_TEST_TOKEN_ADDRESS))
            else:
                session = utils.resilient_session.create_resilient_session()
                session.headers = {"Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"}
                try:
                    response = session.get(url=config.HUB_TEST_TOKEN_ADDRESS, timeout=(5, 5))
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
            with open(settings_path, 'w') as settings_file:  # Caution: everything is automatically lowered...
                parser.write(settings_file)

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
        settings_path = "../" + config.SETTINGS_FILENAME
        parser = ConfigParser(comment_prefixes='/', allow_no_value=True)
        with open(settings_path) as settings_file:
            parser.read_file(settings_file)

        for key, value in data_layer.settings.items():
            os.environ[key] = value
            parser.set('env', key.lower(), value)

        with open(settings_path, 'w') as settings_file:  # Caution: everything is automatically lowered...
            parser.write(settings_file)
        logger.info(f"Successfully updated environment variables and {config.SETTINGS_FILENAME}.")
    except Exception as e:
        logger.error("Could not update and write settings: {0}".format(str(e)))
