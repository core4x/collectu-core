"""
This function sends all registered modules to the hub.
"""
import os
import logging
import pkgutil
import json
from typing import List, Optional

# Internal imports.
import config
import modules

# Third party imports.
import requests

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def start(module_names: Optional[List[str]] = None):
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
                                    .format(module_name, config.HUB_MODULES_ADDRESS, str(response.json().get("id"))))
                    elif not module_exists:
                        # Create the module in the hub.
                        response = s.post(url=config.HUB_MODULES_ADDRESS,
                                          data=json.loads(json.dumps(json.dumps(data))),
                                          allow_redirects=True)
                        response.raise_for_status()
                        logger.info("Successfully created module '{0}' on {1}: {2}"
                                    .format(module_name, config.HUB_MODULES_ADDRESS, str(response.json().get("id"))))
                    else:
                        # Module exists but no changes were detected.
                        logger.info("Module '{0}' already exists and is up to date.".format(module_name))
                except Exception as e:
                    logger.error("Could not send module data ('{0}'): {1}.".format(modname, str(e)),
                                 exc_info=config.EXC_INFO)
