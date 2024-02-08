"""
Command line processor handling arguments given via the cli.

Note: Do not use logging here, since the logging setup was not executed yet.
"""
import sys
import argparse
import os

# Internal imports.
import data_layer
import utils.send_modules_to_hub


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

    group.add_argument('-t', '--test',
                       nargs='?',
                       const='configuration.yml',
                       metavar='configuration.yml',
                       help='executes the application in test mode for a given configuration filename '
                            '(default: configuration.yml)')

    group.add_argument('-s', '--send',
                       nargs='?',
                       const='all',
                       metavar='send all',
                       help='sends all (or the defined) module(s) to the hub')

    args = parser.parse_args()

    if args.modules:
        _command_version(args.modules)
        sys.exit(0)
    if args.about:
        _command_about()
        sys.exit(0)
    if args.run:
        _command_run(args.run)
    if args.cold:
        _command_cold()
    if args.test:
        _command_test(args.test)
    if args.send:
        _command_send(args.send)
        sys.exit(0)


def _command_version(requested_module_type: list[str]):
    """
    Prints all available modules.

    :param requested_module_type: The requested modules. Can be: all, inputs, outputs, or processors.
    """
    for mod_name, module in data_layer.registered_modules.items():
        if "all" in requested_module_type:
            sys.stdout.write(f"{mod_name}: {module.description}\n")
        elif "inputs" in requested_module_type:
            if mod_name.startswith("inputs."):
                sys.stdout.write(f"{mod_name}: {module.description}\n")
        elif "outputs" in requested_module_type:
            if mod_name.startswith("outputs."):
                sys.stdout.write(f"{mod_name}: {module.description}\n")
        elif "processors" in requested_module_type:
            if mod_name.startswith("processors."):
                sys.stdout.write(f"{mod_name}: {module.description}\n")


def _command_about():
    """
    Prints some general information about the app.
    """
    sys.stdout.write(f"{config.APP_NAME}\n")
    sys.stdout.write(f"Version {config.VERSION}\n")
    sys.stdout.write(f"Made by: {config.AUTHOR} ({config.CONTACT})\n")
    sys.stdout.write(f"{config.LICENSE}\n")


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


def _command_test(filename: str):
    """
    Sets the configuration file name and starts the application in test mode.

    :param filename: The filename of the configuration file to be tested.
    """
    # Set the test mode.
    os.environ['TEST'] = "1"
    if os.path.isfile(os.path.join(os.path.dirname(__file__), '..', '..', 'configuration', filename)):
        # Set the given filename as default.
        os.environ['CONFIG'] = filename
    else:
        sys.stderr.write("Please enter an available configuration file name. "
                         "'{0}' could not be found in the configuration directory.\n"
                         .format(filename))
        sys.exit(1)


def _command_send(module_name: str):
    """
    Sends all registered modules to the hub.

    :param module_name: The module to be sent.
    """
    if module_name == "all":
        module_name = None
    else:
        module_name = [module_name]
    utils.send_modules_to_hub.start(module_name)