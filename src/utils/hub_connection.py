"""
Functions to interact with the hub.
"""
import os
import logging
import pkgutil
import json
import importlib
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


def write_module_to_file(module_name: str, module):
    """
    Write the given module to file, or update the existing file.

    :param module_name: The module to write.
    :param module: The module to be written.
    """
    # This is the file path including the file name.
    if module_name.startswith("inputs."):
        path_list = module_name.replace('inputs.', '').split(".")
        path_list[-1] += ".py"
        file = os.path.join('modules', 'inputs', *path_list)
    elif module_name.startswith("outputs."):
        path_list = module_name.replace('outputs.', '').split(".")
        path_list[-1] += ".py"
        file = os.path.join('modules', 'outputs', *path_list)
    elif module_name.startswith("processors."):
        path_list = module_name.replace('processors.', '').split(".")
        path_list[-1] += ".py"
        file = os.path.join('modules', 'processors', *path_list)
    else:
        raise Exception("Unknown module: {0}.".format(module_name))

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
    if "version" in module:
        content = module.get("version").get("code")
    else:
        content = module.get("latest").get("code")

    with open(pathlib.Path(file), 'w', newline='') as f:
        f.write(content)


def download_modules(requested_module_types: str = "all"):
    """
    Download modules from the hub.

    :param requested_module_types: Can be 'all', 'official', or 'my'.
    """
    logger.info("Trying to download {0} modules from {1}."
                .format(requested_module_types, config.HUB_MODULES_ADDRESS))
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
        try:
            params = {}
            if "all" == requested_module_types:
                params["official"] = True
                params["mine"] = True
            elif "my" == requested_module_types:
                params["official"] = False
                params["mine"] = True
            elif "official" == requested_module_types:
                params["official"] = True
                params["mine"] = False
            else:
                logger.error("Invalid module type: {0}.".format(requested_module_types))
                return
            response = s.get(url=f"{config.HUB_MODULES_ADDRESS}/official_and_mine",
                             params=params,
                             allow_redirects=True)
            response.raise_for_status()
            modules = response.json()
            for module in modules:
                if module["module_name"] not in data_layer.registered_modules:
                    download_module(module_name=module.get('module_name'), version=0, session=session)
                elif module["latest"]["version"] != data_layer.registered_modules[module.module_name].version:
                    download_module(module_name=module.get('module_name'), version=0, session=session)
                else:
                    # Module already exists in the latest version.
                    pass
        except Exception as e:
            logger.error("Could not download modules: {0}.".format(str(e)),
                         exc_info=config.EXC_INFO)


def download_module(module_name: Optional[str] = None, version: int = 0, session: requests.Session = None) -> bool:
    """
    Retrieve the given module or all from hub.

    :param module_name: The module to retrieve.
    :param version: The version to retrieve.
    :param session: The optional session instance with authorization header.
    :return: True if the import was successful, False otherwise.
    """
    module_name = module_name.replace(".variable", "").replace(".tag", "")
    logger.info("Trying to download {0} from {1}.".format(module_name, config.HUB_MODULES_ADDRESS))
    no_session = True if session is None else False
    session = session if session else requests.Session()
    with session as s:
        if no_session:
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
            response = s.get(url=f"{config.HUB_MODULES_ADDRESS}/get_public_by_module_name",
                             params={"module_name": module_name, "version": version},
                             allow_redirects=True)
            response.raise_for_status()
            logger.info("Successfully loaded module '{0}' with version {1} from {2} with the id: {3}"
                        .format(module_name,
                                version,
                                config.HUB_MODULES_ADDRESS,
                                str(response.json().get("id"))))
            module = response.json()

            modname = module_name.lower()
            write_module_to_file(module_name=modname, module=module)

            # Import the module.
            imported_module = importlib.import_module("modules." + modname)
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
    if module_names is None:
        for keys in data_layer.registered_modules:
            download_module(keys)
    else:
        for module_name in module_names:
            download_module(module_name)


def send_modules(module_names: Optional[List[str]] = None):
    """
    Updates or creates all registered modules in the hub using the configured user.

    :param module_names: A list with modules names to be sent. If no names are given, all registered modules are sent.
    """
    module_names = [] if module_names is None else module_names
    logger.info("Trying to send {0} modules to {1}.".format(str(len(module_names)), config.HUB_MODULES_ADDRESS))
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
                    data = {"code": pkgutil.get_data(modname, modname.split(".")[-1] + ".py").decode("utf-8"),
                            "official": False}

                    # Check if the module already exists.
                    response = s.get(url=f"{config.HUB_MODULES_ADDRESS}/get_public_by_module_name",
                                     params={"module_name": module_name},
                                     allow_redirects=True)

                    module_exists = False
                    if response.ok:
                        module_exists = True
                        module = response.json()
                    else:
                        logger.info("Module '{0}' does not exist. Trying to create module on hub..."
                                    .format(module_name))

                    if module_exists:
                        # Update the module in the hub.
                        response = s.put(url=f"{config.HUB_MODULES_ADDRESS}/{module.get('id')}",
                                         data=json.loads(json.dumps(json.dumps(data))),
                                         allow_redirects=True)
                        response.raise_for_status()
                        logger.info("Successfully updated module '{0}' on {1}: {2}"
                                    .format(module_name,
                                            config.HUB_MODULES_ADDRESS,
                                            str(response.json().get("id"))))
                    else:
                        # Create the module in the hub.
                        response = s.post(url=config.HUB_MODULES_ADDRESS,
                                          data=json.loads(json.dumps(json.dumps(data | {"module_name": module_name}))),
                                          allow_redirects=True)
                        response.raise_for_status()
                        logger.info("Successfully created module '{0}' on {1}: {2}"
                                    .format(module_name,
                                            config.HUB_MODULES_ADDRESS,
                                            str(response.json().get("id"))))
                    module = response.json()
                    write_module_to_file(module_name=module_name, module=module)
                except Exception as e:
                    logger.error("Could not send module data ('{0}'): {1}.".format(modname, str(e)),
                                 exc_info=config.EXC_INFO)
