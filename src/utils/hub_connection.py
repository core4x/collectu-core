"""
Functions to interact with the hub.
"""
import os
import logging
import re
import json
import pathlib
from typing import List, Optional

# Internal imports.
import config
import data_layer
import utils.resilient_session

# Third party imports.
import requests

import utils.plugin_interface

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def create_authenticated_session() -> requests.Session | None:
    """
    Create an authenticated session using the HUB_API_ACCESS_TOKEN.

    :returns: The authenticated session.
    """
    session = utils.resilient_session.create_resilient_session()
    # Login.
    session.headers = {"Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"}
    # Test the token.
    try:
        response = session.get(url=config.HUB_TEST_TOKEN_ADDRESS,
                               timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
        response.raise_for_status()
        return session
    except Exception as e:
        logger.error("Authentication with hub '{0}' failed. You may be using an invalid api access token: {1}. "
                     "Please check or create an api access token on your hub profile."
                     .format(config.HUB_MODULES_ADDRESS, str(e)), exc_info=config.EXC_INFO)
        return None


MODULE_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "minimal": ("minimal",),
    "standard": ("standard",),
    "my": ("all_my",),
    "official": ("official",),
    "all": ("all_my", "official"),
}
"""The hub endpoints backing each module selection accepted by download_modules."""


def download_modules(requested_module_types: str = "minimal"):
    """
    Download modules from the hub.

    :param requested_module_types: Can be 'minimal', 'standard', 'all', 'official', or 'my'.
    """
    endpoints = MODULE_ENDPOINTS.get(requested_module_types)
    if endpoints is None:
        logger.error("Invalid module type: {0}. Expected one of: {1}."
                     .format(requested_module_types, ", ".join(sorted(MODULE_ENDPOINTS))))
        return

    logger.info("Trying to download {0} modules from {1}."
                .format(requested_module_types, config.HUB_MODULES_ADDRESS))
    session = create_authenticated_session()
    if session is None:
        logger.error("Could not download modules because no valid session could be established.")
        return
    with session as s:
        try:
            modules = []
            for endpoint in endpoints:
                response = s.get(url=f"{config.HUB_MODULES_ADDRESS}/{endpoint}",
                                 # Never install a module this core's own owner is not
                                 # allowed to execute. The hub evaluates its module policy
                                 # against each module's latest version, which is the one
                                 # downloaded below - so what arrives here is what a
                                 # configuration using it would be allowed to run.
                                 # An owner whose policy is `all` (the default) is
                                 # unaffected, and an older hub ignores the parameter.
                                 params={"only_allowed": "true"},
                                 allow_redirects=True,
                                 timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
                response.raise_for_status()
                modules += response.json()

            logger.info("Starting download of {0} modules...".format(len(modules)))
            total = len(modules)
            for idx, module in enumerate(modules, start=1):
                name = module.get('module_name', '<unknown>')
                percent = int(idx / total * 100)
                bar_len = 30
                filled = int(percent / 100 * bar_len)
                bar = '=' * filled + ' ' * (bar_len - filled)
                logger.info(f"[{idx}/{total}] [{bar}] {percent}% - Downloading {name}")
                download_module(module_name=name, version=0, session=s)
            logger.info("Finished download procedure of {0} modules.".format(len(modules)))
        except Exception as e:
            logger.error("Could not download modules: {0}.".format(str(e)),
                         exc_info=config.EXC_INFO)


def _base_name(module_name: str) -> str:
    """
    The module name without the variable/tag suffix a registered input module can carry.

    :param module_name: The module name.
    :return: The name the hub knows the module by.
    """
    return module_name.removesuffix(".variable").removesuffix(".tag")


def _is_newer_than_registered(module: dict) -> bool:
    """
    Whether the module the hub returned is newer than the registered one, or is unknown here.

    :param module: The module as returned by the hub.
    :return: True if it should be written to file.
    """
    hub_name = module.get("module_name")
    registered_versions = [registered.version for name, registered in list(data_layer.registered_modules.items())
                           if _base_name(name) == hub_name]
    if not registered_versions:
        # Not registered at all, so anything the hub has is newer.
        return True
    hub_version = (module.get("version") or module.get("latest") or {}).get("version")
    if hub_version is None:
        # No version to compare against - let the caller write it rather than skip it.
        return True
    return hub_version > max(registered_versions)


def download_module(module_name: str, version: int = 0, session: requests.Session = None) -> bool:
    """
    Retrieve the given module or all from hub.

    :param module_name: The module to retrieve.
    :param version: The version to retrieve.
    :param session: The optional session instance with authorization header.
    :return: True if the import was successful, False otherwise.
    """
    # Remove invisible characters (e.g. zero-width spaces from copy-pasted module names) and surrounding whitespace.
    module_name = _base_name(re.sub("[\u200b\u200c\u200d\u2060\ufeff]", "", module_name).strip())
    logger.info("Trying to download {0} with version {1} from {2}."
                .format(module_name, version, config.HUB_MODULES_ADDRESS))

    session = session if session else create_authenticated_session()
    if session is None:
        logger.error("Could not download module because no valid session could be established.")
        return False

    try:
        response = session.get(url=f"{config.HUB_MODULES_ADDRESS}/get_by_module_name",
                               params={"module_name": module_name, "version": version},
                               allow_redirects=True,
                               timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
        response.raise_for_status()
        logger.info("Successfully downloaded module '{0}' with version {1} from {2} with the id: {3}"
                    .format(module_name,
                            version if version != 0 else "latest",
                            config.HUB_MODULES_ADDRESS,
                            str(response.json().get("id"))))
        module = response.json()

        if not _is_newer_than_registered(module) and version == 0:
            logger.info("Module '{0}' already exists in the latest version. "
                        "Skipping update procedure...".format(module_name))
            return True

        # Save code as file in the given path. The hub answers with the requested
        # 'version' when one was asked for, and with 'latest' otherwise.
        module_code = module.get("version") or module.get("latest") or {}

        # The hub flags a version malicious when its review found malicious intent.
        if module_code.get("malicious"):
            logger.critical("Refused to download module '{0}' with version {1}: the hub has "
                            "flagged this version as malicious."
                            .format(module_name, version if version != 0 else "latest"))
            return False

        code = module_code.get("code")
        if code is None:
            logger.error("Could not download module ('{0}'): the hub response contained no code."
                         .format(module_name))
            return False
        utils.plugin_interface.write_module_to_file(module_name=module_name.lower(), code=code)
        return True
    except Exception as e:
        logger.error("Could not download module ('{0}'): {1}.".format(module_name, str(e)),
                     exc_info=config.EXC_INFO)
        return False


def update_modules(module_names: Optional[List[str]] = None):
    """
    Update the given modules or all.

    :param module_names: A list with modules names to be updated. If none is given, all modules are updated.
    """
    session = create_authenticated_session()
    if session is None:
        logger.error("Could not update modules because no valid session could be established.")
        return None
    if module_names is None:
        module_names = sorted({_base_name(module_name) for module_name in data_layer.registered_modules})
    for module_name in module_names:
        download_module(module_name=module_name, session=session)


def send_modules(module_names: List[str] | None):
    """
    Updates or creates all registered modules in the hub using the configured user.

    :param module_names: A list with modules names to be sent.
    If no names are given, all registered modules in the custom module folder are sent.
    """
    if pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER", ""))).is_dir() and os.environ.get(
            "CUSTOM_MODULE_FOLDER", None):
        custom_folder_path = pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER")))
    else:
        custom_folder_path = None

    if custom_folder_path is None and not module_names:
        logger.error("Can not send all own modules. No custom module folder found. "
                     "Please specify a custom module folder (e.g. in {0}) or specify the module(s) to be sent."
                     .format(config.SETTINGS_FILENAME))
        return

    logger.info("Trying to send {0} to {1}.".format(
        str(len(module_names)) + " module(s)" if module_names else f"all modules in your custom module folder "
                                                                   f"({os.environ.get('CUSTOM_MODULE_FOLDER')})",
        config.HUB_MODULES_ADDRESS))

    session = create_authenticated_session()
    if session is None:
        logger.error("Could not send modules because no valid session could be established.")
        return
    with session as s:

        def find_file(full_relative_path: str, search_dir: str | pathlib.Path = "modules") -> pathlib.Path | None:
            """
            Recursively search for a Python file by its relative path (without .py extension) in a folder.

            :param full_relative_path: The relative path to the file without .py extension (e.g., 'inputs/application/app_status')
            :param search_dir: The directory to be searched at.
            :return: The full path of the file if found, else None
            """
            *relative_dirs, filename_without_extension = full_relative_path.split(os.sep)

            for dirpath, dirnames, filenames in os.walk(search_dir):
                relative_dir = os.path.relpath(dirpath, search_dir)
                if os.path.join(*relative_dirs) in relative_dir:
                    python_filename = f"{filename_without_extension}.py"
                    if python_filename in filenames:
                        return pathlib.Path(os.path.join(dirpath, python_filename))
            return None

        def send_module(module_name: str, code: str):
            """
            Send a specific module to the hub.

            :param module_name: The name of the module to be sent.
            :param code: The code of the module.
            """
            try:
                data = {"code": code,
                        "official": False}
                # Check if the module already exists.
                response = s.get(url=f"{config.HUB_MODULES_ADDRESS}/get_by_module_name",
                                 params={"module_name": module_name},
                                 allow_redirects=True,
                                 timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))

                if response.ok:
                    module = response.json()
                    server_content = module.get("version").get("code")
                    # Remove the version, since this is auto-generated by the server and not the same as locally.
                    pattern = re.compile(r'^{}.*?$'.format('__version__: int ='), re.MULTILINE)
                    server_content_without_version = pattern.sub('', server_content)
                    local_content_without_version = pattern.sub('', data.get("code"))

                    if local_content_without_version != server_content_without_version:
                        # Update the module in the hub. The body is sent as a raw json string,
                        # which is what json.loads(json.dumps(json.dumps(x))) also produced.
                        response = s.put(url=f"{config.HUB_MODULES_ADDRESS}/{module.get('id')}",
                                         data=json.dumps(data),
                                         allow_redirects=True,
                                         timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
                        response.raise_for_status()
                        logger.info("Successfully updated module '{0}' on {1}: {2}"
                                    .format(module_name, config.HUB_MODULES_ADDRESS,
                                            str(response.json().get("id"))))
                    else:
                        logger.info("Module '{0}' seems to be already up to date.".format(module_name))
                        return
                else:
                    logger.info("Module '{0}' does not exist. Trying to create module on hub..."
                                .format(module_name))
                    # Create the module in the hub.
                    response = s.post(url=config.HUB_MODULES_ADDRESS,
                                      data=json.dumps(data | {"module_name": module_name}),
                                      allow_redirects=True,
                                      timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
                    response.raise_for_status()
                    logger.info("Successfully created module '{0}' on {1}: {2}"
                                .format(module_name, config.HUB_MODULES_ADDRESS, str(response.json().get("id"))))

                module = response.json()
                # Save code as file in the given path.
                code = (module.get("version") or module.get("latest") or {}).get("code")
                if code is None:
                    logger.error("Could not store module ('{0}'): the hub response contained no code."
                                 .format(module_name))
                    return
                utils.plugin_interface.write_module_to_file(module_name=module_name, code=code)
            except Exception as e:
                logger.error("Could not send module data ('{0}'): {1}.".format(module_name, str(e)),
                             exc_info=config.EXC_INFO)

        #  1. If no modules are defined, walk through custom modules folder and send all.
        if module_names:
            for module_name in module_names:
                # First we search in the custom module folder if it exists.
                found_path = None
                if custom_folder_path:
                    found_path = find_file(full_relative_path=module_name.replace(".", os.sep),
                                           search_dir=custom_folder_path)
                if found_path is None:
                    # If we have not found it in the custom folder path, we search the complete directory.
                    found_path = find_file(full_relative_path=module_name.replace(".", os.sep),
                                           search_dir="modules")
                if found_path is None:
                    logger.error("Could not find module: {0}".format(module_name))
                else:
                    send_module(module_name=module_name, code=found_path.read_text(encoding="utf-8"))
        #  2. If modules are defined, search in both module folders and send them (if found in custom, prefer this one).
        else:
            for module_name, values in utils.plugin_interface.get_all_custom_module_files().items():
                send_module(module_name=module_name, code=values.get("code"))
