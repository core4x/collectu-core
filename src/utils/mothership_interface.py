"""
The mothership functionality provides an interface to other apps,
which allow to check the current status or remote control of this app.
"""
import os
from typing import List, Dict, Any
import json
from threading import Thread
from datetime import datetime, timezone
import time
import logging
import pathlib

# Internal imports.
import config
import data_layer
import models
import utils.updater
import utils.plugin_interface

# Third party imports.
import requests
import tinydb

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


class DatabaseWorker:
    """
    A database worker to be thread safe during the file operations.
    This worker continuously checks data_layer.mothership_data for changes and applies them to the db file.
    """

    def __init__(self):
        # Create directory for the database if it does not exist.
        pathlib.Path(os.path.join('..', 'data', 'mothership')).mkdir(parents=True, exist_ok=True)
        # Create the path to the database.
        self.db_path = os.path.join('..', 'data', 'mothership', 'mothership.db')
        # Instantiate the database.
        self.db = tinydb.TinyDB(self.db_path)
        # First we add all existing database entries to the data_layer.
        for app in self.db:
            data_layer.mothership_data[app.get("id")] = models.MothershipData(
                status="unknown",  # This will be updated if we receive a report.
                version=app.get("version"),
                description=app.get("description"),
                last_update=datetime.fromisoformat(app.get("last_update")))

        Thread(target=self._checker,
               daemon=False,
               name="Mothership_DB_Worker").start()

    def _checker(self):
        """
        Gets continuously (with sleep time) executed in a separate thread and does the following two things:

        1. Updates the db files if a new reporter id sends data and updates existing db entries,
           if a reporter app description changes.

        2. Resets the status of reporters in the data.mothership_data,
           if after a configured time, no new data was received.
        """
        while data_layer.running:
            try:
                # Get the mothership data entries.
                for app_id, mothership_data in data_layer.mothership_data.copy().items():
                    entry = self.db.get(tinydb.where('id') == app_id)
                    if entry is not None:
                        # Check if description, version, or last_update changed.
                        if mothership_data.description != entry.get("description") or \
                                mothership_data.version != entry.get("version") or \
                                mothership_data.last_update > datetime.fromisoformat(entry.get("last_update")):
                            self.db.update({"description": mothership_data.description,
                                            "version": mothership_data.version,
                                            "last_update": mothership_data.last_update.isoformat()},
                                           tinydb.where('id') == app_id)
                    else:
                        self.db.insert({"id": app_id,
                                        "description": mothership_data.description,
                                        "version": mothership_data.version,
                                        "last_update": mothership_data.last_update.isoformat()})

                    # Reset status if we received no update in a configured time.
                    if (datetime.now(timezone.utc) - mothership_data.last_update).seconds > config.REPORTER_TIMEOUT:
                        if app_id in data_layer.mothership_data:
                            data_layer.mothership_data[app_id].status = "unknown"

                # Delete app ids from db, if they are no longer in the data.mothership_data dict.
                # This can be the case, if a user deletes the key (using the according rest endpoint).
                for entry in self.db:
                    if entry.get("id") not in data_layer.mothership_data:
                        self.db.remove(tinydb.where('id') == entry.get("id"))
            except Exception as e:
                logger.error("Could not interact with mothership db '{0}': {1}".format(str(self.db_path), str(e)),
                             exc_info=config.EXC_INFO)
            time.sleep(1)


def start():
    """
    Start to send messages to the motherships and request todos from them.
    """
    # Get all configured motherships.
    motherships: List[str] = json.loads(os.environ.get('MOTHERSHIPS', "[]"))
    """All configured mothership addresses."""

    # Instantiate the db worker and load all existing entries of the db into data.mothership_data.
    DatabaseWorker()

    session = requests.Session()
    session.headers.update({'Accept': 'application/json', 'Content-Type': 'application/json'})

    if bool(int(os.environ.get('REPORT_TO_HUB', '1'))) and os.environ.get('HUB_API_ACCESS_TOKEN', None):
        logger.info(f"Started mothership communication to {config.HUB_APP_ADDRESS}.")
        Thread(target=_report_hub,
               daemon=True,
               name="Mothership_Hub_Report_Worker").start()
        time.sleep(3)  # We have to wait before requesting tasks, until the initial app was created.
        Thread(target=_request_hub_tasks,
               daemon=True,
               name="Mothership_Hub_Request_Worker").start()
    elif bool(int(os.environ.get('REPORT_TO_HUB', '1'))) and not os.environ.get('HUB_API_ACCESS_TOKEN', None):
        logger.error("REPORT_TO_HUB is enabled, but no valid HUB_API_ACCESS_TOKEN is set. "
                     "Please create and insert a valid api access token in settings.ini.")

    for mothership in motherships:
        Thread(target=_report,
               args=(session, mothership,),
               daemon=True,
               name="Mothership_Report_Worker_{0}".format(mothership)).start()
        Thread(target=_request_todos,
               args=(session, mothership,),
               daemon=True,
               name="Mothership_Request_Worker_{0}".format(mothership)).start()

        logger.info(f"Started mothership communication to {mothership}.")


def _get_report_data() -> Dict[str, Any]:
    """
    Create the data to be sent to the motherships.

    :return: A dictionary containing the
    """
    # We always have to send the complete information, since we do not know if the mothership has restarted.
    mothership_data = {
        # Determine the status of the app (check if modules are configured).
        "status": "running" if len(data_layer.module_data) > 0 else "inactive",
        "version": data_layer.version,
        "description": os.environ.get("APP_DESCRIPTION", "-"),
        "configuration": getattr(data_layer.configuration, "configuration_dict", [])
    }

    # Get the new logs.
    simplified_logs = []
    for log in data_layer.latest_logs.copy():
        # Create the simplified log data object.
        simplified_log = models.Log(level=log.fields.get("level"),
                                    message=log.fields.get("message"),
                                    module=log.fields.get("module"),
                                    name=log.fields.get("name"),
                                    time=str(log.time))
        simplified_logs.append(simplified_log.__dict__)

    mothership_data["latest_logs"] = simplified_logs

    return mothership_data


def _report_hub():
    """
    Sends post request containing current app data cyclically to the hub.
    This function is called in a separate thread.
    """
    start_time = datetime.now()
    logged_in = False
    session = requests.Session()

    while data_layer.running:
        if not logged_in:
            try:
                session.headers = {}
                logged_in = True
                session.headers.update({"Accept": "application/json",
                                        "Content-Type": "application/json",
                                        "Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"})
                # Test the token.
                response = session.post(url=config.HUB_TEST_TOKEN_ADDRESS, timeout=(5, 5))
                response.raise_for_status()
            except Exception as e:
                send = False
                if config.HUB_APP_ADDRESS + "_login" in data_layer.last_mothership_sending_error_log:
                    last_sending = datetime.now() - data_layer.last_mothership_sending_error_log[
                        config.HUB_APP_ADDRESS + "_login"]
                    if config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL < float(last_sending.seconds):
                        send = True
                else:
                    send = True

                if send:
                    data_layer.last_mothership_sending_error_log[
                        config.HUB_APP_ADDRESS + "_login"] = datetime.now()
                    logger.error("Invalid api access token for requesting tasks on {0}: {1}. "
                                 "Please check or create an api access token on your hub profile. "
                                 "You can also turn off the reporting functionality ('report_to_hub') "
                                 "in your settings.ini."
                                 .format(config.HUB_APP_ADDRESS, str(e)), exc_info=config.EXC_INFO)
                logged_in = False
        if logged_in:
            try:
                json_data = _get_report_data()
                json_data["app_id"] = os.environ.get("APP_ID")
                response = session.post(url=f"{config.HUB_APP_ADDRESS}",
                                        timeout=(5, 5),
                                        json=json.loads(json.dumps(json_data, default=str)))
                response.raise_for_status()
            except Exception as e:
                logged_in = False
                send = False
                if config.HUB_APP_ADDRESS in data_layer.last_mothership_sending_error_log:
                    last_sending = datetime.now() - data_layer.last_mothership_sending_error_log[
                        config.HUB_APP_ADDRESS]
                    if config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL < float(last_sending.seconds):
                        send = True
                else:
                    send = True

                if send:
                    data_layer.last_mothership_sending_error_log[config.HUB_APP_ADDRESS] = datetime.now()
                    logger.error("Could not send report to mothership '{0}': {1}"
                                 .format(config.HUB_APP_ADDRESS, str(e)), exc_info=config.EXC_INFO)

        required_time = datetime.now() - start_time
        if config.REPORT_INTERVAL > float(required_time.seconds):
            time.sleep(config.REPORT_INTERVAL - float(required_time.seconds))
            start_time = datetime.now()
        else:
            start_time = datetime.now()


def _request_hub_tasks():
    """
    Send get request (requesting new todos) cyclically to the mothership.

    The requested json body can contain the following commands:

    {
    "command": "restart, start, stop, save, load, or update",
    "configuration": [json_config]  # If 'load' or 'save' is the command.
    "git_access_token": str  # if 'update' is the command. Is optional!
    }
    """
    start_time = datetime.now()
    session = requests.Session()
    logged_in = False

    while data_layer.running:
        if not logged_in:
            # Login.
            try:
                session.headers = {}
                logged_in = True
                session.headers.update({"Accept": "application/json",
                                        "Content-Type": "application/json",
                                        "Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"})
                # Test the token.
                response = session.post(url=config.HUB_TEST_TOKEN_ADDRESS, timeout=(5, 5))
                response.raise_for_status()
            except Exception as e:
                send = False
                if config.HUB_TASK_ADDRESS + "_login" in data_layer.last_mothership_receiving_error_log:
                    last_sending = datetime.now() - data_layer.last_mothership_receiving_error_log[
                        config.HUB_TASK_ADDRESS + "_login"]
                    if config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL < float(last_sending.seconds):
                        send = True
                else:
                    send = True

                if send:
                    data_layer.last_mothership_receiving_error_log[
                        config.HUB_TASK_ADDRESS + "_login"] = datetime.now()
                    logger.error("Invalid api access token for requesting tasks on {0}: {1}. "
                                 "Please check or create an api access token on your hub profile. "
                                 "You can also turn off the reporting functionality ('report_to_hub') "
                                 "in your settings.ini."
                                 .format(config.HUB_TASK_ADDRESS, str(e)), exc_info=config.EXC_INFO)
                logged_in = False
        if logged_in:
            try:
                response = session.get(url=f'{config.HUB_TASK_ADDRESS}/{os.environ.get("APP_ID")}',
                                       timeout=(5, 5))
                response.raise_for_status()
                json_response = response.json()

                for task in json_response:
                    command = task.get("command", None)
                    logger.info("Received task '{0}' from hub '{1}'.".format(command, config.HUB_APP_ADDRESS))
                    if command == "restart":
                        utils.updater.restart_application()
                    elif command == "start":
                        data_layer.configuration.restart()
                    elif command == "stop":
                        data_layer.configuration.stop()
                    elif command == "update":
                        git_access_token = task.get("git_access_token", None)
                        if git_access_token:
                            # A git access token was passed. Store it as file.
                            with open("../git_access_token.txt", 'w') as file:
                                logger.info("Successfully updated git_access_key.txt file with your git token.")
                                file.write(git_access_token)
                        utils.updater.update_app_with_git()
                    elif command == "load":
                        errors = data_layer.configuration.load_configuration_from_stream(
                            content=json.dumps(task.get("configuration")))
                        if errors:
                            logger.error(
                                "The following errors occurred while trying to deserialize the configuration:\n" +
                                "\n".join("{}: {}".format(k, v) for k, v in errors.items()))
                            continue
                    elif command == "save":
                        success, error = data_layer.configuration.save_configuration_as_file(content=json.dumps(task.get("configuration")))
                        if not success:
                            logger.error("Could not save file: {0}".format(error))
                    else:
                        logger.error("Received task with unknown command: '{0}' from hub '{1}'."
                                     .format(command, config.HUB_APP_ADDRESS))

            except Exception as e:
                logged_in = False
                send = False
                if config.HUB_TASK_ADDRESS in data_layer.last_mothership_receiving_error_log:
                    last_sending = datetime.now() - data_layer.last_mothership_receiving_error_log[
                        config.HUB_TASK_ADDRESS]
                    if config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL < float(last_sending.seconds):
                        send = True
                else:
                    send = True

                if send:
                    data_layer.last_mothership_receiving_error_log[config.HUB_TASK_ADDRESS] = datetime.now()
                    logger.error("Could not request or process task from hub '{0}': {1}"
                                 .format(config.HUB_APP_ADDRESS, str(e)), exc_info=config.EXC_INFO)

        required_time = datetime.now() - start_time
        if config.REQUEST_INTERVAL > float(required_time.seconds):
            time.sleep(config.REQUEST_INTERVAL - float(required_time.seconds))
            start_time = datetime.now()
        else:
            start_time = datetime.now()


def _report(session: requests.Session, mothership: str):
    """
    Sends post request containing current app data cyclically to the mothership.
    This function is called in a separate thread.

    :param session: The request session.
    :param mothership: The mothership address.
    """
    start_time = datetime.now()

    while data_layer.running and session:
        try:
            response = session.post(url=f"{mothership}/api/v1/mothership/report/{os.environ.get('APP_ID')}",
                                    timeout=(5, 5),
                                    json=json.dumps(_get_report_data(), default=str))
            response.raise_for_status()
        except Exception as e:
            send = False
            if mothership in data_layer.last_mothership_sending_error_log:
                last_sending = datetime.now() - data_layer.last_mothership_sending_error_log[mothership]
                if config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL < float(last_sending.seconds):
                    send = True
            else:
                send = True

            if send:
                data_layer.last_mothership_sending_error_log[mothership] = datetime.now()
                logger.error("Could not send report to mothership '{0}': {1}"
                             .format(mothership, str(e)), exc_info=config.EXC_INFO)

        required_time = datetime.now() - start_time
        if config.REPORT_INTERVAL > float(required_time.seconds):
            time.sleep(config.REPORT_INTERVAL - float(required_time.seconds))
            start_time = datetime.now()
        else:
            start_time = datetime.now()


def _request_todos(session: requests.Session, mothership):
    """
    Send get request (requesting new todos) cyclically to the mothership.

    The requested json body can contain the following commands:

    {
    "command": "restart, start, save, stop, load, or update",
    "configuration": [json_config]  # If 'load' or 'save' is the command.
    "git_access_token": str  # if 'update' is the command. Is optional!
    }

    :param session: The request session.
    :param mothership: The mothership address.
    """
    start_time = datetime.now()
    while data_layer.running and session:
        try:
            response = session.get(url=f"{mothership}/api/v1/mothership/todo/{os.environ.get('APP_ID')}",
                                   timeout=(5, 5),
                                   headers={'Accept': 'application/json', 'Content-Type': 'application/json'})

            if response.status_code != 404:
                response.raise_for_status()
                json_response = response.json()

                command = json_response.get("command", None)
                if command is not None:
                    logger.info("Received task '{0}' from mothership '{1}'.".format(command, mothership))
                    if command == "restart":
                        utils.updater.restart_application()
                    if command == "start":
                        data_layer.configuration.restart()
                    if command == "stop":
                        data_layer.configuration.stop()
                    if command == "update":
                        git_access_token = json_response.get("git_access_token", None)
                        if git_access_token:
                            # A git access token was passed. Store it as file.
                            with open("../git_access_token.txt", 'w') as file:
                                logger.info("Successfully updated git_access_key.txt file with your git token.")
                                file.write(git_access_token)
                        utils.updater.update_app_with_git()
                    if command == "load":
                        errors = data_layer.configuration.load_configuration_from_stream(
                            content=json.dumps(json_response.get("configuration")))
                        if errors:
                            logger.error(
                                "The following errors occurred while trying to deserialize the configuration:\n" +
                                "\n".join("{}: {}".format(k, v) for k, v in errors.items()))
                            continue
                    if command == "save":
                        data_layer.configuration.save_configuration_as_file(
                            content=json.dumps(json_response.get("configuration")))

        except Exception as e:
            send = False
            if mothership in data_layer.last_mothership_receiving_error_log:
                last_sending = datetime.now() - data_layer.last_mothership_receiving_error_log[mothership]
                if config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL < float(last_sending.seconds):
                    send = True
            else:
                send = True

            if send:
                data_layer.last_mothership_receiving_error_log[mothership] = datetime.now()
                logger.error("Could not request or process todos from mothership '{0}': {1}"
                             .format(mothership, str(e)), exc_info=config.EXC_INFO)

        required_time = datetime.now() - start_time
        if config.REQUEST_INTERVAL > float(required_time.seconds):
            time.sleep(config.REQUEST_INTERVAL - float(required_time.seconds))
            start_time = datetime.now()
        else:
            start_time = datetime.now()
