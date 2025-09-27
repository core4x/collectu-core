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

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""

# Third-party imports (optional).
try:
    import markdown
except ImportError as e:
    markdown = None
    logger.error("Optional markdown package not installed! Some features may not be supported.")

try:
    from packaging.requirements import Requirement
    from packaging.version import parse as parse_version
except ImportError as e:
    Requirement = None
    logger.error("Optional packaging package not installed! Some features may not be supported.")


def install_plugin_requirement(package: str) -> int:
    """
    Checks and installs the given requirement if necessary.

    - Supports pip-style specifiers (==, >=, <=, >, <, ~=, !=, and composite ones like 'pkg>=1.0,<2.0').
    - If `packaging` is available it will check the installed version and skip pip if already satisfied.
    - If `packaging` is not available it will fall back to calling `pip install <package>` directly
      (pip itself will report "Requirement already satisfied" when appropriate).

    :param package: The requirement string (e.g. "Flask==2.0.2", "requests>=2.0", "Django>=3.0,<4.0").
    :returns: The return code. 0 if successful, otherwise non-zero.
    """
    try:
        # If packaging is available, try to parse the requirement and check installed version first.
        if Requirement is not None:
            try:
                req = Requirement(package)
            except Exception:
                # malformed requirement string — fall back to pip
                req = None

            if req is not None:
                pkg_name = req.name  # canonical package name (without extras/specifiers).
                specifier = req.specifier  # SpecifierSet (may be empty).

                # Try to get installed version.
                try:
                    installed_version = importlib.metadata.version(pkg_name)
                except importlib.metadata.PackageNotFoundError:
                    installed_version = None

                if installed_version is not None and (
                        not specifier or specifier.contains(parse_version(installed_version), prereleases=True)):
                    logger.info("Package '%s' already installed (version %s satisfies '%s').", pkg_name,
                                installed_version, str(specifier) or "any")
                    return 0
                # else: either not installed or installed version doesn't satisfy; we'll call pip below.

        # Either packaging isn't available, or we determined installation is needed.
        # Use pip to install. We pass the original package string to pip so extras/specifiers remain intact.
        result = subprocess.run([sys.executable, "-m", "pip", "install", package],
                                capture_output=True, text=True, check=True)
        if result.returncode != 0:
            logger.error("Could not install package '%s': %s", package, result.stderr)
        else:
            logger.info("Successfully installed '%s'. %s", package, result.stdout.splitlines()[:1])
        return result.returncode

    except Exception as e:
        logger.error("Something went wrong while trying to install package '%s': %s", package, str(e),
                     exc_info=config.EXC_INFO)
        return 1


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


def get_list_of_all_module_requirements() -> list[dict]:
    """
    Get the third party module requirements.

    :returns: A list of all module requirements.
    """
    requirements = []
    for module_name, module_class in data_layer.registered_modules.items():
        requirements += module_class.third_party_requirements
    requirements = list(set(requirements))
    requirements = sorted(requirements, key=str.lower)
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
                    modname = module_path.split(".", 2)[-1].lower()

                    if modname in data_layer.registered_modules:
                        logger.warning("A module with the name {0} was already registered and "
                                       "is now overwritten with the one in your custom module folder ({1})."
                                       .format(modname, os.environ.get("CUSTOM_MODULE_FOLDER")))
                    if modname.startswith("inputs."):
                        if hasattr(module, "InputModule"):
                            data_layer.registered_modules[modname] = getattr(module, "InputModule")
                        if hasattr(module, "VariableModule"):
                            if modname + ".variable" in data_layer.registered_modules:
                                logger.warning("A module with the name {0} was already registered and "
                                               "is now overwritten with the one in your custom module folder ({1})."
                                               .format(modname + ".variable", os.environ.get("CUSTOM_MODULE_FOLDER")))
                            data_layer.registered_modules[modname + ".variable"] = getattr(module, "VariableModule")
                        if hasattr(module, "TagModule"):
                            if modname + ".tag" in data_layer.registered_modules:
                                logger.warning("A module with the name {0} was already registered and "
                                               "is now overwritten with the one in your custom module folder ({1})."
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


def get_all_module_files() -> dict[str, dict[str, Any]]:
    """
    Get all modules (in the module folder).

    The value dict has the following entries:
    - code
    - path

    :returns: A dict containing the module name as key and some attributes as value.
    """
    found_modules: dict[str, dict[str, Any]] = {}
    for dirpath, dirnames, filenames in os.walk("modules"):
        for filename in filenames:
            if filename.endswith('.py') and filename != "__init__.py":
                found_path = pathlib.Path(os.path.join(dirpath, filename))
                module_name = dirpath.replace("modules", "").replace(os.sep, ".")[1:] + "." + filename[:-3]
                if (module_name.startswith("processors.") or
                        module_name.startswith("inputs.") or
                        module_name.startswith("outputs.")):
                    found_modules[module_name] = {"code": open(found_path, encoding="utf-8").read(),
                                                  "path": found_path}
    return found_modules


def get_all_custom_module_files() -> dict[str, dict[str, Any]]:
    """
    Get all custom modules (in the custom module folder).
    If no custom module folder exists, and empty dict is returned.

    The value dict has the following entries:
    - code
    - path

    :returns: A list containing the module name as key and some attributes as value.
    """
    if pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER", ""))).is_dir() and os.environ.get(
            "CUSTOM_MODULE_FOLDER", None):
        custom_folder_path = pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER")))
    else:
        return {}

    found_modules: dict[str, dict[str, Any]] = {}
    for dirpath, dirnames, filenames in os.walk(custom_folder_path):
        for filename in filenames:
            if filename.endswith('.py') and filename != "__init__.py" and (pathlib.Path(
                    os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER"), "inputs")).is_relative_to(
                custom_folder_path) or pathlib.Path(
                os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER"), "outputs")).is_relative_to(
                custom_folder_path) or pathlib.Path(
                os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER"),
                             "processors")).is_relative_to(custom_folder_path)):
                found_path = pathlib.Path(os.path.join(dirpath, filename))
                module_name = dirpath.replace(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER")),
                                              "").replace(os.sep, ".")[1:] + "." + filename[:-3]
                found_modules[module_name] = {"code": open(found_path, encoding="utf-8").read(),
                                              "path": found_path}
    return found_modules


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

        # Use markdown only if available.
        documentation_html = markdown.markdown(
            getattr(sys.modules[module.__module__], "__doc__", "")) if markdown else getattr(
            sys.modules[module.__module__], "__doc__", "")

        data = {"module_name": module_name,
                "module_type": module_type,
                # "installed": installed,
                "version": module.version,
                "public": module.public,
                "author": module.author,
                "email": module.email,
                "description": module.description,
                "documentation": getattr(sys.modules[module.__module__], "__doc__", ""),
                "documentation_html": documentation_html,
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


def dynamically_import_module(module_path: str):
    """
    Dynamically import given module.

    :param module_path: The path to the module.
    """
    module_path = module_path.replace(os.sep, '.')
    if module_path.endswith(".py"):
        module_path = module_path[:-3]
    imported_module = importlib.import_module(module_path)
    # If the module already exists before updating, we have to reload it.
    imported_module = importlib.reload(imported_module)

    modname = module_path.replace("modules.", "", 1) if module_path.startswith("modules.") else module_path

    # Register the module.
    if modname.startswith("inputs."):
        if hasattr(imported_module, "InputModule"):
            data_layer.registered_modules[modname] = getattr(imported_module, "InputModule")
        if hasattr(imported_module, "VariableModule"):
            data_layer.registered_modules[modname + ".variable"] = getattr(imported_module,
                                                                           "VariableModule")
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

    logger.info("Successfully imported {0} with version: {1}."
                .format(modname, imported_module.__version__))


def write_module_to_file(module_name: str, code: str, import_module: bool = True):
    """
    Write the given module to file, or update the existing file and import the module.

    :param module_name: The module to write.
    :param code: The module code to be written.
    :param import_module: Do you want to directly import the module.
    """
    # Check if a custom module folder exists.
    if pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER", ""))).is_dir() and os.environ.get(
            "CUSTOM_MODULE_FOLDER", None):
        custom_folder_path = pathlib.Path(os.path.join("modules", os.environ.get("CUSTOM_MODULE_FOLDER")))
    else:
        custom_folder_path = None

    # This is the file path including the file name.
    file = None
    if module_name.startswith("inputs."):
        path_list = module_name.replace('inputs.', '').split(".")
        path_list[-1] += ".py"
        if custom_folder_path is not None:
            # Check if the module exists in the custom module folder.
            if os.path.isfile(os.path.join(custom_folder_path, 'inputs', *path_list)):
                file = os.path.join(custom_folder_path, 'inputs', *path_list)
        if not file:
            file = os.path.join('modules', 'inputs', *path_list)
    elif module_name.startswith("outputs."):
        path_list = module_name.replace('outputs.', '').split(".")
        path_list[-1] += ".py"
        if custom_folder_path is not None:
            # Check if the module exists in the custom module folder.
            if os.path.isfile(os.path.join(custom_folder_path, 'outputs', *path_list)):
                file = os.path.join(custom_folder_path, 'outputs', *path_list)
        if not file:
            file = os.path.join('modules', 'outputs', *path_list)
    elif module_name.startswith("processors."):
        path_list = module_name.replace('processors.', '').split(".")
        path_list[-1] += ".py"
        if custom_folder_path is not None:
            # Check if the module exists in the custom module folder.
            if os.path.isfile(os.path.join(custom_folder_path, 'processors', *path_list)):
                file = os.path.join(custom_folder_path, 'processors', *path_list)
        if not file:
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
        if os.path.basename(current_dir) == os.environ.get("CUSTOM_MODULE_FOLDER", None):
            break
        init_py_path = os.path.join(current_dir, '__init__.py')
        if not os.path.isfile(init_py_path):
            open(init_py_path, "a").close()
        if os.path.basename(current_dir) == "modules":
            break
        if current_dir == '/':
            break
        current_dir = os.path.dirname(current_dir)

    if os.path.isfile(file):
        logger.warning("File '{0}' already exists and is now overwritten.".format(file))

    with open(pathlib.Path(file), 'w', newline='', encoding='utf-8', errors='ignore') as f:
        f.write(code)
    logger.info("Successfully wrote code to file: {0}".format(file))
    if import_module:
        dynamically_import_module(module_path=file)
