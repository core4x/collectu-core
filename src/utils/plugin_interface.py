"""
Handles requirements of the module plugins.
"""
import subprocess
import os
import sys
import importlib
import importlib.util
import importlib.metadata
import pathlib
import pkgutil
import logging
from typing import Any
from dataclasses import _MISSING_TYPE

# Internal imports.
import config
import data_layer
import modules

# Third party imports.
import markdown

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def install_plugin_requirement(package: str):
    """
    Installs the given requirement.

    :param package: The requirement to be installed (e.g. "Flask==2.0.2").

    :returns: The return code. 0 if successful, otherwise 1.
    """
    return_code = 1
    try:
        # Check if it is already installed.
        installed_packages = {pkg.metadata['Name'].lower(): pkg.version for pkg in importlib.metadata.distributions()}
        # Check if the package is already installed with the correct version.
        if '==' in package:
            package_name, version = package.split('==')
        else:
            package_name = package
            version = None
        installed_version = installed_packages.get(package_name.lower())
        if not installed_version or (version and installed_version != version):
            result = subprocess.run([sys.executable, "-m", "pip", "install", package],
                                    capture_output=True, text=True, check=True)
            return_code = result.returncode
            if return_code != 0:
                logger.error("Could not install package '{0}': {1}".format(package, str(result.stderr)))
            else:
                logger.info("Successfully installed '{0}'.".format(package))
        else:
            logger.info("Package '{0}' already installed.".format(package))
            return_code = 0
    except subprocess.CalledProcessError as e:
        logger.error("Something went wrong while trying to install package '{0}': {1}".format(package, str(e)),
                     exc_info=config.EXC_INFO)
        return_code = 1
    finally:
        return return_code


def get_plugin_requirement_status() -> list[dict]:
    """
    Receive information about the current status of the installation of the input and output modules.
    The lists contain dicts with the following information:

    {"name": "inputs.opc_ua.opc_ua_client_1",
     "description" "text",
     "requirements": List[str],
     "installed": True/False}

    :returns: List of dictionaries containing the requirement information.
    """
    requirements = []
    for module_name, module_class in data_layer.registered_modules.items():
        try:
            installed = module_class.import_third_party_requirements()
        except ImportError:
            installed = False
        requirements.append({"name": module_name,
                             "description": module_class.description,
                             "requirements": module_class.third_party_requirements,
                             "installed": installed})
    return requirements


def load_modules():
    """
    Load and register all available modules.
    """
    # First: Load all modules from the general modules packages.
    for importer, modname, ispackage in pkgutil.walk_packages(path=modules.__path__,
                                                              prefix=modules.__name__ + '.',
                                                              onerror=lambda x: None):
        if not ispackage:
            try:
                module = importlib.import_module(modname)
                modname = modname.replace("modules.", "").lower()
                if modname.startswith("inputs."):
                    if hasattr(module, "InputModule"):
                        data_layer.registered_modules[modname] = getattr(module, "InputModule")
                    if hasattr(module, "VariableModule"):
                        data_layer.registered_modules[modname + ".variable"] = getattr(module, "VariableModule")
                    if hasattr(module, "TagModule"):
                        data_layer.registered_modules[modname + ".tag"] = getattr(module, "TagModule")
                elif modname.startswith("outputs."):
                    if hasattr(module, "OutputModule"):
                        data_layer.registered_modules[modname] = getattr(module, "OutputModule")
                elif modname.startswith("processors."):
                    if hasattr(module, "ProcessorModule"):
                        data_layer.registered_modules[modname] = getattr(module, "ProcessorModule")
                else:
                    logger.debug("Unknown module: {0}.".format(modname))
            except Exception as e:
                logger.warning("Could not import and register module '{0}': {1}".format(str(modname), str(e)),
                               exc_info=config.EXC_INFO)
        else:
            # Here, we have all packages (folders with __init__.py file).
            # logger.debug(modname)
            pass

    # Second: Load (and overwrite if it already exists) all modules from the custom module folder if defined.
    if pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER", ""))).is_dir() and os.environ.get(
            "CUSTOM_MODULE_FOLDER", None):
        package_path = pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER"))).resolve()
        sys.path.append(str(package_path))
        try:
            top_package = importlib.import_module("modules." + os.environ.get("CUSTOM_MODULE_FOLDER"))
            logger.info("Successfully imported custom module package: modules.{0}"
                        .format(os.environ.get("CUSTOM_MODULE_FOLDER")))
        except ModuleNotFoundError as e:
            logger.error("Failed to import custom module package '{0}': {1}"
                         .format(os.environ.get("CUSTOM_MODULE_FOLDER"), str(e)))
            return

        package_path = pathlib.Path(top_package.__path__[0])
        # Walk through the directory tree.
        for dir_path, _, filenames in os.walk(package_path):
            for filename in filenames:
                if filename.endswith('.py') and filename != '__init__.py':
                    relative_dir = os.path.relpath(dir_path, package_path)
                    module_name = os.path.splitext(filename)[0]
                    # Convert the file path to a module path.
                    if relative_dir != '.':
                        module_path = f"modules.{os.path.basename(package_path)}.{relative_dir.replace(os.sep, '.')}.{module_name}"
                    else:
                        module_path = f"modules.{os.path.basename(package_path)}.{module_name}"
                    # Dynamically import the module.
                    logger.debug("Importing custom module: {0}".format(module_path))
                    module = importlib.import_module(module_path)
                    module = importlib.reload(module)
                    modname = module_path.replace("modules.",
                                                  "").replace(f"{os.environ.get('CUSTOM_MODULE_FOLDER')}.",
                                                              "").lower()

                    if modname in data_layer.registered_modules:
                        logger.warning("A module with the name {0} was already registered and "
                                       "is now overwritten with the one in your custom module folder: {1}"
                                       .format(modname, os.environ.get("CUSTOM_MODULE_FOLDER")))
                    if modname.startswith("inputs."):
                        if hasattr(module, "InputModule"):
                            data_layer.registered_modules[modname] = getattr(module, "InputModule")
                        if hasattr(module, "VariableModule"):
                            if modname + ".variable" in data_layer.registered_modules:
                                logger.warning("A module with the name {0} was already registered and "
                                               "is now overwritten with the one in your custom module folder: {1}"
                                               .format(modname + ".variable", os.environ.get("CUSTOM_MODULE_FOLDER")))
                            data_layer.registered_modules[modname + ".variable"] = getattr(module, "VariableModule")
                        if hasattr(module, "TagModule"):
                            if modname + ".tag" in data_layer.registered_modules:
                                logger.warning("A module with the name {0} was already registered and "
                                               "is now overwritten with the one in your custom module folder: {1}"
                                               .format(modname + ".tag", os.environ.get("CUSTOM_MODULE_FOLDER")))
                            data_layer.registered_modules[modname + ".tag"] = getattr(module, "TagModule")
                    elif modname.startswith("outputs."):
                        if hasattr(module, "OutputModule"):
                            data_layer.registered_modules[modname] = getattr(module, "OutputModule")
                    elif modname.startswith("processors."):
                        if hasattr(module, "ProcessorModule"):
                            data_layer.registered_modules[modname] = getattr(module, "ProcessorModule")
                    else:
                        logger.debug("Unknown module: {0}.".format(modname))

    logger.info("Successfully registered {0} modules.".format(str(len(data_layer.registered_modules))))


def get_all_modules(inputs: bool = False, outputs: bool = False, processors: bool = False) -> list[dict[str, Any]]:
    """
    Get all modules.
    If one of the arguments (inputs, outputs, processors) is True, the filter functionality is applied.
    If all are False, everything is included.

    :param inputs: True, to include input modules.
    :param outputs: True, to include output modules.
    :param processors: True, to include processor modules.

    :returns: A list containing all modules with the following content:

    {"module_name": "module_name",
     "module_type": Union["input", "output", "processor"],
     "version": 1,
     "public": True/False
     "author": "author",
     "email": "email",
     "description": "description",
     "documentation": "documentation as markdown",
     "documentation_html": "documentation as html",
     "deprecated": True/False,
     "third_party_requirements": list[str],
     "parameters": parameter_list}

     In addition, the following optional keys can be contained:

     For output modules:
     - "can_be_buffer": True/False

    For processor modules:
     - "field_requirements": list[str]
     - "tag_requirements": list[str]

    The parameter_list contains dicts with the following content.

     {"key": field_name,
      "data_type": "data_type",
      "required": True/False,
      "description": "description",
      "default": "default_value",
      "dynamic": True/False}
    """
    modules = []
    for module_name, module in data_layer.registered_modules.items():
        # Apply the filter functionality.
        if processors and not module_name.startswith("processors."):
            continue
        if inputs and not module_name.startswith("inputs."):
            continue
        if outputs and not module_name.startswith("outputs."):
            continue

        parameter_list = []
        for field_name, field in getattr(module, "Configuration").__dataclass_fields__.items():
            # Get the default value.
            if type(field.default) != _MISSING_TYPE:
                default_value = field.default
            elif type(field.default_factory) != _MISSING_TYPE:
                default_value = field.default_factory()
            else:
                default_value = None
            parameter_list.append({"key": field_name,
                                   "data_type": str(getattr(field, "type")).replace("typing.", "") if getattr(
                                       getattr(getattr(field, "type"), "__class__"), "__name__") != "type" else str(
                                       getattr(getattr(field, "type"), "__name__")),
                                   "required": field.metadata.get("required", False),
                                   "description": field.metadata.get("description", "-"),
                                   "default": default_value,
                                   "dynamic": field.metadata.get('dynamic', False)}, )
        """ No longer used, since this takes a lot of time.
        try:
            installed = module.import_third_party_requirements()
        except ImportError:
            installed = False
        """
        if module_name.startswith("inputs."):
            module_type = "input"
        elif module_name.startswith("outputs."):
            module_type = "output"
        elif module_name.startswith("processors."):
            module_type = "processor"
        else:
            logger.error("Unknown module type for module '{0}'".format({module_name}))
            continue
        data = {"module_name": module_name,
                "module_type": module_type,
                # "installed": installed,
                "version": module.version,
                "public": module.public,
                "author": module.author,
                "email": module.email,
                "description": module.description,
                "documentation": getattr(sys.modules[module.__module__], "__doc__", ""),
                "documentation_html": markdown.markdown(getattr(sys.modules[module.__module__], "__doc__", "")),
                "deprecated": module.deprecated,
                "third_party_requirements": module.third_party_requirements,
                "parameters": parameter_list}

        if module_name.startswith("outputs."):
            data["can_be_buffer"] = getattr(module, "can_be_buffer", False)
        if module_name.startswith("processors."):
            data["field_requirements"] = getattr(module, "field_requirements", [])
            data["tag_requirements"] = getattr(module, "tag_requirements", [])

        modules.append(data)
    return modules
