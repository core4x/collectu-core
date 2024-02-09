"""
Functions to interact with the hub.
"""
import os
import logging
import pkgutil
import json
import importlib
import sys
import pathlib
from typing import List, Optional

# Internal imports.
import config
import data_layer
import modules

# Third party imports.
import requests

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def download_module(module_name: Optional[str] = None) -> bool:
    """
    Retrieve the given module or all from hub.

    :param module_name: The module to retrieve.
    :return: True if the import was successful, False otherwise.
    """
    module_name = module_name.replace(".variable", "").replace(".tag", "")
    logger.info("Trying to download {0} from {1}.".format(module_name, config.HUB_MODULES_ADDRESS))
    session = requests.Session()
    with session as s:
        # Login.
        session.headers = {"Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"}
        # Test the token.
        try:
            response = session.post(url=config.HUB_TEST_TOKEN_ADDRESS)
            response.raise_for_status()
        except Exception as e:
            logger.error("Invalid api access token for {0}: {1}. "
                         "Please check or create an api access token on your hub profile."
                         .format(config.HUB_MODULES_ADDRESS, str(e)), exc_info=config.EXC_INFO)
            return False
        try:
            # Update the module in the hub.
            response = s.get(url=f"{config.HUB_MODULES_ADDRESS}/get_public_by_module_name",
                             params={"module_name": module_name},
                             allow_redirects=True)
            response.raise_for_status()
            logger.info("Successfully loaded module '{0}' from {1} with the id: {2}"
                        .format(module_name,
                                config.HUB_MODULES_ADDRESS,
                                str(response.json().get("id"))))
            module = response.json()

            modname = module_name.lower()
            # This is the file path including the file name.
            if modname.startswith("inputs."):
                path_list = modname.replace('inputs.', '').split(".")
                path_list[-1] += ".py"
                file = os.path.join('modules', 'inputs', *path_list)
            elif modname.startswith("outputs."):
                path_list = modname.replace('outputs.', '').split(".")
                path_list[-1] += ".py"
                file = os.path.join('modules', 'outputs', *path_list)
            elif modname.startswith("processors."):
                path_list = modname.replace('processors.', '').split(".")
                path_list[-1] += ".py"
                file = os.path.join('modules', 'processors', *path_list)
            else:
                logger.error("Unknown module: {0}.".format(modname))

            # Create directory.
            pathlib.Path(os.path.join(str(pathlib.Path(file).parents[0]))).mkdir(
                parents=True,
                exist_ok=True)

            # Check if __init__.py files exist in all folders on the path. Otherwise, create them.
            current_dir = os.path.dirname(file)
            while True:
                init_py_path = os.path.join(current_dir, '__init__.py')
                if not os.path.isfile(init_py_path):
                    open(init_py_path, "a").close()
                if os.path.basename(current_dir) == "modules":
                    break
                if current_dir == '/':
                    break
                current_dir = os.path.dirname(current_dir)

            # Save code as file in the given path.
            with open(pathlib.Path(file), 'w', newline='') as f:
                f.write(module.get("code"))

            # Import the module.
            imported_module = importlib.import_module("modules." + module_name)
            # Register the module.
            if modname.startswith("inputs."):
                if hasattr(imported_module, "InputModule"):
                    data_layer.registered_modules[modname] = getattr(imported_module, "InputModule")
                if hasattr(imported_module, "VariableModule"):
                    data_layer.registered_modules[modname + ".variable"] = getattr(imported_module, "VariableModule")
                if hasattr(imported_module, "TagModule"):
                    data_layer.registered_modules[modname + ".tag"] = getattr(imported_module, "TagModule")
            elif modname.startswith("outputs."):
                if hasattr(imported_module, "OutputModule"):
                    data_layer.registered_modules[modname] = getattr(imported_module, "OutputModule")
            elif modname.startswith("processors."):
                if hasattr(imported_module, "ProcessorModule"):
                    data_layer.registered_modules[modname] = getattr(imported_module, "ProcessorModule")
            else:
                logger.error("Unknown module: {0}.".format(modname))

            logger.info("Successfully downloaded, created, and imported {0}".format(module_name))
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
    # TODO
    raise NotImplementedError


def send_modules(module_names: Optional[List[str]] = None):
    """
    Updates or creates all registered modules in the hub using the configured user.

    :param module_names: A list with modules names to be sent. If no names are given, all registered modules are sent.
    """
    module_names = [] if module_names is None else module_names
    session = requests.Session()
    with session as s:
        # Login.
        session.headers = {"Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"}
        # Test the token.
        try:
            response = session.post(url=config.HUB_TEST_TOKEN_ADDRESS)
            response.raise_for_status()
        except Exception as e:
            logger.error("Invalid api access token for {0}: {1}. "
                         "Please check or create an api access token on your hub profile."
                         .format(config.HUB_MODULES_ADDRESS, str(e)), exc_info=config.EXC_INFO)
            return
        for importer, modname, ispackage in pkgutil.walk_packages(path=modules.__path__,
                                                                  prefix=modules.__name__ + '.',
                                                                  onerror=lambda x: None):
            if not ispackage and (not module_names or modname.replace("modules.", "").lower() in module_names):
                try:
                    module_name = modname.replace("modules.", "").lower()
                    data = {"module_name": module_name,
                            "code": pkgutil.get_data(modname, modname.split(".")[-1] + ".py").decode("utf-8"),
                            "official": False}

                    # Check if the module already exists.
                    response = s.get(url=f"{config.HUB_MODULES_ADDRESS}/get_my_by_module_name/",
                                     params={"module_name": module_name},
                                     allow_redirects=True)

                    changes = False
                    module_exists = False
                    if response.ok:
                        module_exists = True
                        module = response.json()
                        # Compare the modules, if a module of the user with this module_name already exists.
                        if module.get("code", None) != data.get("code"):
                            changes = True
                        if module.get("official", None) != data.get("official"):
                            changes = True
                        if changes:
                            logger.info("Identified changes for module '{0}'. Trying to update module..."
                                        .format(module_name))
                    else:
                        logger.info("Module '{0}' does not exist. Trying to create module on hub..."
                                    .format(module_name))

                    if changes:
                        # Update the module in the hub.
                        response = s.put(url=f"{config.HUB_MODULES_ADDRESS}/{module.get('id')}",
                                         data=json.loads(json.dumps(json.dumps(data))),
                                         allow_redirects=True)
                        response.raise_for_status()
                        logger.info("Successfully updated module '{0}' on {1}: {2}"
                                    .format(module_name,
                                            config.HUB_MODULES_ADDRESS,
                                            str(response.json().get("id"))))
                    elif not module_exists:
                        # Create the module in the hub.
                        response = s.post(url=config.HUB_MODULES_ADDRESS,
                                          data=json.loads(json.dumps(json.dumps(data))),
                                          allow_redirects=True)
                        response.raise_for_status()
                        logger.info("Successfully created module '{0}' on {1}: {2}"
                                    .format(module_name,
                                            config.HUB_MODULES_ADDRESS,
                                            str(response.json().get("id"))))
                    else:
                        # Module exists but no changes were detected.
                        logger.info("Module '{0}' already exists and is up to date.".format(module_name))
                except Exception as e:
                    logger.error("Could not send module data ('{0}'): {1}.".format(modname, str(e)),
                                 exc_info=config.EXC_INFO)
