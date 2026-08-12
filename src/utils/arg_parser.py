"""
Command line processor handling arguments given via the cli.

Note: Do not use logging here, since the logging setup was not executed yet.
"""
import sys
import argparse
import os

# Internal imports.
import config
import data_layer
import utils.hub_connection
import utils.updater


def process_commands():
    """
    Process arguments given in the command line.
    """
    parser = argparse.ArgumentParser(description='The Command Line Interface.')

    # Create a group, which accepts only one argument by once.
    group = parser.add_mutually_exclusive_group()

    group.add_argument('-m', '--modules',
                       nargs='+',
                       choices=['all', 'inputs', 'outputs', 'processors'],
                       help='returns all available modules')

    group.add_argument('-a', '--about',
                       action='store_true',
                       help='returns general information about the application')

    group.add_argument('-r', '--run',
                       nargs='?',
                       const='configuration.yml',
                       metavar='configuration.yml',
                       help='executes the application for a given configuration filename (default: configuration.yml)')

    group.add_argument('-c', '--cold',
                       action='store_true',
                       help='starts the api and frontend without loading a configuration')

    group.add_argument('-s', '--send_modules',
                       nargs='?',
                       const='all',
                       metavar='send all',
                       help='sends all (or the defined) module(s) to the hub')

    group.add_argument('-u', '--update',
                       action='store_true',
                       help='updates the app and all submodules')

    group.add_argument('-l', '--download_modules',
                       nargs=1,
                       choices=['all', 'my', 'official'],
                       help='downloads modules from the hub')

    group.add_argument('-d', '--update_modules',
                       nargs='?',
                       const='all',
                       metavar='all or the modules names',
                       help='updates all or the specified module')

    args = parser.parse_args()

    if args.modules:
        _command_modules(args.modules)
        sys.exit(0)
    if args.about:
        _command_about()
        sys.exit(0)
    if args.run:
        _command_run(args.run)
    if args.cold:
        _command_cold()
    if args.send_modules:
        _command_send_modules(args.send_modules)
        sys.exit(0)
    if args.update:
        _command_update()
        sys.exit(0)
    if args.download_modules:
        _command_download_modules(args.download_modules)
        sys.exit(0)
    if args.update_modules:
        _command_update_modules(args.update_modules)
        sys.exit(0)


def _command_modules(requested_module_types: list[str]):
    """
    Prints all available modules.

    :param requested_module_types: The requested module types.
    Can be: all, and/or any of inputs, outputs, processors.
    """
    if "all" in requested_module_types:
        selected = data_layer.registered_modules.items()
    else:
        prefixes = tuple(f"{module_type}." for module_type in requested_module_types)
        selected = [(mod_name, module) for mod_name, module in data_layer.registered_modules.items()
                    if mod_name.startswith(prefixes)]

    for mod_name, module in selected:
        sys.stdout.write(f"{mod_name}: {module.description}\n")


def _command_about():
    """
    Prints some general information about the app.
    """
    sys.stdout.write(f"{config.APP_NAME}\n")
    sys.stdout.write(f"{config.CONTACT}\n")


def _command_cold():
    """
    Only the start the api and frontend and do not load the configuration.
    """
    os.environ['API'] = "1"
    os.environ['FRONTEND'] = "1"
    os.environ['AUTO_START'] = "0"


def _command_run(filename: str):
    """
    Sets the configuration file name when application is started via cli.

    :param filename: The filename of the configuration file to be executed.
    """
    if os.path.isfile(os.path.join(os.path.dirname(__file__), '..', '..', 'configuration', filename)):
        # Set the given filename as default.
        os.environ['CONFIG'] = filename
    else:
        sys.stderr.write("Please enter an available configuration file name. "
                         "'{0}' could not be found in the configuration directory.\n"
                         .format(filename))
        sys.exit(1)


def _command_send_modules(module_name: str):
    """
    Sends all registered modules to the hub.

    :param module_name: The module to be sent.
    """
    if module_name == "all":
        module_name = None
    else:
        module_name = [module_name]
    utils.hub_connection.send_modules(module_names=module_name)


def _command_update():
    """
    Update the app.
    """
    utils.updater.update_app()


def _command_download_modules(requested_module_type: list[str]):
    """
    Downloads modules of the requested type from the hub.

    :param requested_module_type: A single-element list holding 'all', 'my', or 'official'.
    """
    utils.hub_connection.download_modules(requested_module_types=requested_module_type[0])


def _command_update_modules(module_name: str):
    """
    Updates the given module, or all registered ones, from the hub.

    :param module_name: The module to update, or 'all'.
    """
    if module_name == "all":
        module_names = None
    else:
        module_names = [module_name]
    utils.hub_connection.update_modules(module_names=module_names)
