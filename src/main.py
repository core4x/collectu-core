"""
This is an application, which collects or receives data from various input modules
specified in a configuration file. The received data can be processed and dynamically tagged.
Subsequently, the data is stored in defined output modules.

For further information please see README.md.
"""
import os
import sys
import logging
import time
import atexit

# Internal imports. Caution: Make sure we have set the environment variables, before you (globally) try to access them.
import config
import utils.logging
import utils.initialization
import data_layer
import configuration
import utils.arg_parser
import utils.mothership_interface
import utils.usage_statistics
import utils.updater
import utils.plugin_interface
import utils.hub_connection
import models

logger = logging.getLogger(config.APP_NAME.lower())
"""The logger instance."""


def exit_handler():
    """
    This functions gets called when the application exits.

    Note: The exit function is not called when the program is killed by a signal,
    when a Python fatal internal error is detected, or when os._exit() is called.
    """
    logger.info("Thank you for using {0}!".format(config.APP_NAME))


# This is the entrypoint of the application.
if __name__ == "__main__":
    # Set /src as working directory.
    os.chdir(sys.path[0])

    # Check the python version.
    if sys.version_info < (3, 10):
        raise Exception("Python 3.10 or a more recent version is required. We recommend Python 3.11.")

    # Set up the logging.
    utils.logging.start(logger)

    # Exit handler.
    atexit.register(exit_handler)

    # Check if all requirements of third party packages are met.
    utils.initialization.check_installed_app_packages()
    # Set the default environment variables and install plugins defined in the settings file.
    settings_updated = utils.initialization.load_and_process_settings_file()

    # Load all available modules.
    utils.plugin_interface.load_modules()

    # Check if additional commands are given.
    utils.arg_parser.process_commands()

    if bool(int(os.environ.get('INITIAL_DOWNLOAD', '1'))) and (
            settings_updated or len(data_layer.registered_modules) == 0):
        if bool(os.environ.get('HUB_API_ACCESS_TOKEN', False)):
            utils.hub_connection.download_modules(requested_module_types="all")
        else:
            logger.warning("Could not initially download modules from hub since no HUB_API_ACCESS_TOKEN "
                           "was provided in settings.ini.")

    if bool(int(os.environ.get('API', '1'))):
        # Once we set up the logger and initialized everything, we can import the other things.
        # This guarantees, that we already have set all environment variables.
        try:
            import interface.api_v1.app

            # Start the API.
            interface.api_v1.app.start()
        except Exception as e:
            logger.error("Could not start api. Do you have a valid license?".format(str(e)),
                         exc_info=config.EXC_INFO)

    if bool(int(os.environ.get('FRONTEND', '1'))):
        if not bool(int(os.environ.get('API', '1'))):
            logger.warning("The API is disabled. "
                           "Some features, such as mothership functionality, are not supported without the API.")
        try:
            import interface.frontend_v1.app

            # Start the frontend.
            interface.frontend_v1.app.start()
        except Exception as e:
            logger.error("Could not start frontend. Do you have a valid license?".format(str(e)),
                         exc_info=config.EXC_INFO)

    # Start the mothership reporting.
    utils.mothership_interface.start()

    # Initialize the usage statistic sender.
    if bool(int(os.environ.get("SEND_USAGE_STATISTICS", '1'))):
        utils.usage_statistics.Statistics()

    commits = utils.updater.check_for_updates_with_git()
    if commits:
        logger.warning(f"{commits} update(s) can be applied.")
    elif commits == 0:
        logger.info(f"{config.APP_NAME} is up to date.")

    # Initialize the configuration.
    configuration.Configuration()

    # This loop is needed to keep the main script alive. Otherwise, the application and all daemon threads are closed.
    timer: int = 60
    """Time in seconds a function below will be called."""
    counter: int = timer
    while data_layer.running:
        try:
            if counter >= timer:
                counter = 0
                # This is called every 'timer' seconds.
            counter += 1
            time.sleep(1)
        except KeyboardInterrupt:
            # Stop all running modules.
            data_layer.configuration.stop()
            # Stop all processes and other loops.
            data_layer.running = False
            sys.exit(0)
