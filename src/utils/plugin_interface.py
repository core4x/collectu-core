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
except ImportError:
    markdown = None
    logger.warning("Optional markdown package not installed! Some features may not be supported.")

try:
    from packaging.requirements import Requirement
    from packaging.version import parse as parse_version
except ImportError:
    Requirement = None
    logger.warning("Optional packaging package not installed! Some features may not be supported.")


def get_custom_module_folder() -> pathlib.Path | None:
    """
    The configured custom module folder, if it is set and exists.

    :returns: The path to the custom module folder, or None.
    """
    custom_module_folder = os.environ.get("CUSTOM_MODULE_FOLDER", "")
    if not custom_module_folder:
        return None
    path = pathlib.Path(os.path.join("modules", custom_module_folder))
    return path if path.is_dir() else None


def module_registry_entries(modname: str, module: Any) -> list[tuple[str, Any]]:
    """
    The data_layer.registered_modules entries an imported module file provides.

    An input file can hold up to three module classes, which is why the mapping between a
    file and the entries it produces is kept in one place.

    :param modname: The dotted module name, e.g. 'inputs.opc_ua.opc_ua_client'.
    :param module: The imported module object.

    :returns: A list of (registry key, module class) pairs, empty for an unknown module type.
    """
    if modname.startswith("inputs."):
        attributes = [("InputModule", modname),
                      ("VariableModule", modname + ".variable"),
                      ("TagModule", modname + ".tag")]
    elif modname.startswith("outputs."):
        attributes = [("OutputModule", modname)]
    elif modname.startswith("processors."):
        attributes = [("ProcessorModule", modname)]
    else:
        return []

    return [(registry_key, getattr(module, attribute))
            for attribute, registry_key in attributes if hasattr(module, attribute)]


def register_module(modname: str, module: Any) -> bool:
    """
    Register the module classes an imported module file exposes.

    :param modname: The dotted module name, e.g. 'inputs.opc_ua.opc_ua_client'.
    :param module: The imported module object.

    :returns: True if at least one module class was registered.
    """
    entries = module_registry_entries(modname, module)
    for registry_key, module_class in entries:
        data_layer.registered_modules[registry_key] = module_class
    return bool(entries)


def requirement_is_installed(package: str) -> tuple[bool, str]:
    """
    Checks whether the given requirement is already satisfied by the current environment.

    - Requires the `packaging` library. If unavailable, always returns ``False``.
    - Supports pip-style specifiers (==, >=, <=, >, <, ~=, !=, and composites like
      'pkg>=1.0,<2.0').

    :param package: The requirement string (e.g. "Flask==2.0.2", "requests>=2.0").
    :returns: A tuple of (satisfied, message) where satisfied is ``True`` if the
              requirement is met, and message describes the result or reason for failure.
    """
    if Requirement is None:
        return False, "Cannot check requirement '{0}': 'packaging' library is not installed.".format(package)

    try:
        req = Requirement(package)
    except Exception:
        return False, "Malformed requirement string '{0}'.".format(package)

    pkg_name = req.name        # Canonical package name (without extras/specifiers).
    specifier = req.specifier  # SpecifierSet (may be empty).

    try:
        installed_version = importlib.metadata.version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        return False, "Requirement '{0}' is not installed.".format(pkg_name)

    if not specifier or specifier.contains(parse_version(installed_version), prereleases=True):
        return True, "Requirement '{0}' is satisfied (installed: {1}).".format(package, installed_version)

    return False, "Requirement '{0}' is not satisfied (installed: {1}).".format(package, installed_version)


def install_plugin_requirement(package: str) -> int:
    """
    Installs the given requirement if necessary.

    Calls :func:`requirement_is_installed` first and skips pip when the requirement is
    already satisfied. If `packaging` is not available it falls back to calling
    ``pip install <package>`` directly (pip itself will report
    "Requirement already satisfied" when appropriate).

    :param package: The requirement string (e.g. "Flask==2.0.2", "requests>=2.0",
                    "Django>=3.0,<4.0").
    :returns: Return code — ``0`` on success, non-zero on failure.
    """
    try:
        satisfied, _ = requirement_is_installed(package)

        if satisfied:
            logger.info("Package '{0}' is already installed, skipping installation.".format(package))
            return 0
        elif not bool(int(os.environ.get('AUTO_INSTALL', '0'))):
            logger.critical("Package installation for '{0}' needed but AUTO_INSTALL is disabled."
                            .format(package))
            return 1

        logger.info("Trying to install package '{0}'...".format(package))

        # Either packaging isn't available, or we determined installation is needed.
        # Use pip to install. We pass the original package string to pip so extras/specifiers remain intact.
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--force-reinstall", package],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("Successfully installed '{0}'. {1}".format(package, result.stdout.splitlines()[:1]))
            return 0
        except subprocess.CalledProcessError as e:
            logger.error("Could not install package '{0}': {1}".format(package, e.stderr))
            return 1
    except Exception as e:
        logger.error("Something went wrong while trying to install package '{0}': {1}"
                     .format(package, e), exc_info=config.EXC_INFO)
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
        installed: bool = True
        try:
            module_class.import_third_party_requirements()
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
                if not register_module(modname, module):
                    logger.debug("Unknown module: {0}.".format(modname))
            except Exception as e:
                logger.warning("Could not import and register module '{0}': {1}".format(str(modname), str(e)),
                               exc_info=config.EXC_INFO)
        else:
            # Here, we have all packages (folders with __init__.py file).
            # logger.debug(modname)
            pass

    # Second: Load (and overwrite if it already exists) all modules from the custom module folder if defined.
    custom_module_folder = get_custom_module_folder()
    if custom_module_folder is not None:
        package_path = custom_module_folder.resolve()
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
                    # Dynamically import the module. Wrapped like the general module loop
                    # above: one custom module that fails to import used to abort the walk,
                    # so every module after it in the folder went unregistered as well.
                    logger.debug("Importing custom module: {0}".format(module_path))
                    modname = module_path.split(".", 2)[-1].lower()
                    try:
                        module = importlib.import_module(module_path)
                        module = importlib.reload(module)  # Required if it is just a hot-reload.
                    except Exception as e:
                        logger.warning("Could not import and register custom module '{0}': {1}"
                                       .format(module_path, str(e)), exc_info=config.EXC_INFO)
                        continue

                    entries = module_registry_entries(modname, module)
                    if not entries:
                        logger.debug("Unknown module: {0}.".format(modname))
                    for registry_key, module_class in entries:
                        if registry_key in data_layer.registered_modules:
                            logger.warning("A module with the name {0} was already registered and "
                                           "is now overwritten with the one in your custom module folder ({1})."
                                           .format(registry_key, os.environ.get("CUSTOM_MODULE_FOLDER")))
                        data_layer.registered_modules[registry_key] = module_class

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
                    found_modules[module_name] = {"code": found_path.read_text(encoding="utf-8"),
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
    custom_folder_path = get_custom_module_folder()
    if custom_folder_path is None:
        return {}

    found_modules: dict[str, dict[str, Any]] = {}
    inputs_root = custom_folder_path / "inputs"
    outputs_root = custom_folder_path / "outputs"
    processors_root = custom_folder_path / "processors"
    for dirpath, dirnames, filenames in os.walk(custom_folder_path):
        for filename in filenames:
            dir_path_obj = pathlib.Path(dirpath)
            is_module_dir = (
                    dir_path_obj.is_relative_to(inputs_root)
                    or dir_path_obj.is_relative_to(outputs_root)
                    or dir_path_obj.is_relative_to(processors_root)
            )
            if filename.endswith('.py') and filename != "__init__.py" and is_module_dir:
                found_path = pathlib.Path(os.path.join(dirpath, filename))
                module_name = dirpath.replace(str(custom_folder_path), "").replace(os.sep, ".")[1:] \
                    + "." + filename[:-3]
                found_modules[module_name] = {"code": found_path.read_text(encoding="utf-8"),
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
      "category": "basic/advanced/...",
      "secret": True/False,
      "description": "description",
      "default": "default_value",
      "dynamic": True/False}
    """
    described_modules = []
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
                                   "category": field.metadata.get("category", "basic").lower(),
                                   "description": field.metadata.get("description", "-"),
                                   "secret": field.metadata.get("secret", False),
                                   "default": default_value,
                                   "dynamic": field.metadata.get('dynamic', False)}, )

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

        described_modules.append(data)
    return described_modules


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
    if not register_module(modname, imported_module):
        logger.error("Unknown module: {0}.".format(modname))

    logger.info("Successfully imported {0} with version: {1}."
                .format(modname, getattr(imported_module, "__version__", "unknown")))


def write_module_to_file(module_name: str, code: str, import_module: bool = True):
    """
    Write the given module to file, or update the existing file and import the module.

    :param module_name: The module to write.
    :param code: The module code to be written.
    :param import_module: Do you want to directly import the module.
    """
    # Check if a custom module folder exists.
    custom_folder_path = get_custom_module_folder()

    module_type = module_name.split(".", 1)[0]
    if module_type not in ("inputs", "outputs", "processors"):
        raise Exception("Unknown module: {0}.".format(module_name))

    path_list = module_name.split(".")[1:]
    path_list[-1] += ".py"

    # This is the file path including the file name. An existing file in the custom module
    # folder wins, so an update lands on the copy that is actually being loaded.
    file = None
    if custom_folder_path is not None:
        custom_file = os.path.join(custom_folder_path, module_type, *path_list)
        if os.path.isfile(custom_file):
            file = custom_file
    if not file:
        file = os.path.join('modules', module_type, *path_list)

    # Create directory.
    pathlib.Path(file).parent.mkdir(parents=True, exist_ok=True)

    # Check if __init__.py files exist in all folders on the path. Otherwise, create them.
    current_dir = os.path.dirname(file)
    while current_dir:
        if os.path.basename(current_dir) == os.environ.get("CUSTOM_MODULE_FOLDER", None):
            break
        init_py_path = os.path.join(current_dir, '__init__.py')
        if not os.path.isfile(init_py_path):
            open(init_py_path, "a").close()
        if os.path.basename(current_dir) == "modules":
            break
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir

    if os.path.isfile(file):
        logger.warning("File '{0}' already exists and is now overwritten.".format(file))

    with open(pathlib.Path(file), 'w', newline='', encoding='utf-8', errors='ignore') as f:
        f.write(code)
    logger.info("Successfully wrote code to file: {0}".format(file))
    if import_module:
        dynamically_import_module(module_path=file)
