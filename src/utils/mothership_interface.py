"""
The mothership functionality provides an interface to other apps,
which allow to check the current status or remote control of this app.
"""
import os
from typing import List, Dict, Any, Optional, Tuple
import json
from threading import Thread
from datetime import datetime, timezone
import time
import logging
import pathlib
import platform
import shutil
import importlib.metadata

# Internal imports.
import utils.config_store
import config
import data_layer
import metrics
import models
import utils.updater
import utils.security
import utils.resilient_session

# Third party imports.
import requests

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def _allowed_commands() -> List[str]:
    """
    The commands a mothership is permitted to execute on this app.

    An unset or empty ALLOWED_COMMANDS permits all commands in order to be backward compatible.

    :return: The allowed command names.
    """
    return [item.strip() for item in os.environ.get("ALLOWED_COMMANDS", "").split(",") if
                             item] if os.environ.get("ALLOWED_COMMANDS", "") else []


def _log_error_throttled(log_times: Dict[str, datetime], key: str, message: str):
    """
    Log an error, but at most once per STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL and key.

    An unreachable mothership is retried every few seconds. Without this, one that stays down
    writes the same line to the log - and into the buffer that gets reported to the hub - until
    it comes back.

    :param log_times: The registry of last log times, either for sending or for receiving.
    :param key: Identifies the error stream, usually the mothership address.
    :param message: The message to log.
    """
    last_logged = log_times.get(key)
    if last_logged is not None and \
            (datetime.now() - last_logged).total_seconds() < config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL:
        return
    log_times[key] = datetime.now()
    logger.error(message, exc_info=config.EXC_INFO)


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
        self.db = utils.config_store.open_store(self.db_path, description="the mothership peer registry")
        # First we add all existing database entries to the data_layer.
        for app in self.db:
            data_layer.mothership_data[app.get("id")] = models.MothershipData(
                app_id=app.get("id"),
                status="unknown",  # This will be updated if we receive a report.
                version=app.get("version"),
                description=app.get("description"),
                updated_at=datetime.fromisoformat(app.get("updated_at")),
                created_at=datetime.fromisoformat(app.get("created_at")),
                hostname=app.get("hostname"),
                os=app.get("os"),
                cpu_count=app.get("cpu_count"),
                cpu_architecture=app.get("cpu_architecture"),
                python_version=app.get("python_version"),
                disk_total_gb=app.get("disk_total_gb"),
                disk_used_gb=app.get("disk_used_gb"),
                disk_free_gb=app.get("disk_free_gb"),
                processed_per_min_min=app.get("processed_per_min_min"),
                processed_per_min_max=app.get("processed_per_min_max"),
                processed_per_min_avg=app.get("processed_per_min_avg"),
                module_count=app.get("module_count"))

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
                    entry = self.db.get('id', app_id)
                    if entry is not None:
                        # Check if description, version, or updated_at changed.
                        if mothership_data.description != entry.get("description") or \
                                mothership_data.version != entry.get("version") or \
                                mothership_data.updated_at > datetime.fromisoformat(entry.get("updated_at")):
                            data = {"description": mothership_data.description,
                                    "version": mothership_data.version,
                                    "updated_at": mothership_data.updated_at.isoformat(),
                                    "hostname": mothership_data.hostname,
                                    "os": mothership_data.os,
                                    "cpu_count": mothership_data.cpu_count,
                                    "cpu_architecture": mothership_data.cpu_architecture,
                                    "python_version": mothership_data.python_version,
                                    "disk_total_gb": mothership_data.disk_total_gb,
                                    "disk_used_gb": mothership_data.disk_used_gb,
                                    "disk_free_gb": mothership_data.disk_free_gb,
                                    "processed_per_min_min": mothership_data.processed_per_min_min,
                                    "processed_per_min_max": mothership_data.processed_per_min_max,
                                    "processed_per_min_avg": mothership_data.processed_per_min_avg,
                                    "module_count": mothership_data.module_count}
                            self.db.update(data, 'id', app_id)
                    else:
                        data = {"id": app_id,
                                "description": mothership_data.description,
                                "version": mothership_data.version,
                                "created_at": mothership_data.created_at.isoformat(),
                                "updated_at": mothership_data.updated_at.isoformat(),
                                "hostname": mothership_data.hostname,
                                "os": mothership_data.os,
                                "cpu_count": mothership_data.cpu_count,
                                "cpu_architecture": mothership_data.cpu_architecture,
                                "python_version": mothership_data.python_version,
                                "disk_total_gb": mothership_data.disk_total_gb,
                                "disk_used_gb": mothership_data.disk_used_gb,
                                "disk_free_gb": mothership_data.disk_free_gb,
                                "processed_per_min_min": mothership_data.processed_per_min_min,
                                "processed_per_min_max": mothership_data.processed_per_min_max,
                                "processed_per_min_avg": mothership_data.processed_per_min_avg,
                                "module_count": mothership_data.module_count}
                        self.db.insert(data)

                    # Reset status if we received no update in a configured time.
                    if (datetime.now(timezone.utc) - mothership_data.updated_at).total_seconds() > \
                            config.REPORTER_TIMEOUT:
                        if app_id in data_layer.mothership_data:
                            data_layer.mothership_data[app_id].status = "unknown"

                # Delete app ids from db, if they are no longer in the data.mothership_data dict.
                # This can be the case, if a user deletes the key (using the according rest endpoint).
                # Over a snapshot: removing from the table while iterating it skips
                # the entry that moves into the freed slot.
                for entry in self.db.all():
                    if entry.get("id") not in data_layer.mothership_data:
                        self.db.remove('id', entry.get("id"))
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
                     "Please create and provide a valid api access token.")

    for mothership in motherships:
        Thread(target=_report,
               args=(mothership,),
               daemon=True,
               name="Mothership_Report_Worker_{0}".format(mothership)).start()
        Thread(target=_request_tasks,
               args=(mothership,),
               daemon=True,
               name="Mothership_Request_Worker_{0}".format(mothership)).start()

        logger.info(f"Started mothership communication to {mothership}.")


def _get_system_stats() -> Dict[str, Any]:
    """
    Gather cross-platform system statistics using only standard library modules.

    :return: Dictionary containing hostname, OS, CPU info, and disk usage.
    """
    stats: Dict[str, Any] = {}
    try:
        stats["hostname"] = platform.node()
        stats["os"] = platform.platform()
        stats["cpu_count"] = os.cpu_count()
        stats["cpu_architecture"] = platform.machine()
        stats["python_version"] = platform.python_version()
    except Exception as e:
        logger.error("Could not get general system statistics: {0}".format(str(e)), exc_info=config.EXC_INFO)

    try:
        # Get disk usage for the current working directory path
        path = os.getcwd()
        disk_usage = shutil.disk_usage(path)
        stats["disk_total_gb"] = round(disk_usage.total / (1024 ** 3), 2)
        stats["disk_used_gb"] = round(disk_usage.used / (1024 ** 3), 2)
        stats["disk_free_gb"] = round(disk_usage.free / (1024 ** 3), 2)
    except Exception as e:
        logger.error("Could not get disk statistics: {0}".format(str(e)), exc_info=config.EXC_INFO)

    return stats


def _get_installed_packages() -> List[models.InstalledPackage]:
    """
    List the distributions installed in this app's Python environment.

    This is what the hub needs for an "as-deployed" software bill of materials: a module
    declares third-party requirements, but an unpinned requirement resolves to whatever pip
    found at install time on this particular device, so only the device knows the real
    versions.

    The result is sorted by name, so an unchanged environment always serializes identically
    and the caller can skip resending it.

    :return: The installed packages, sorted by lowercased name.
    """
    packages: List[models.InstalledPackage] = []
    try:
        seen: set = set()
        for distribution in importlib.metadata.distributions():
            try:
                name = distribution.metadata["Name"]
                if not name:
                    continue
                # A path with several entries for one distribution (an editable install
                # shadowing a wheel, for example) would otherwise report it twice.
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                packages.append(models.InstalledPackage(name=name,
                                                        version=distribution.version or "unknown"))
            except Exception:
                # One unreadable dist-info directory must not cost us the whole inventory.
                continue
        packages.sort(key=lambda package: package.name.lower())
    except Exception as e:
        logger.error("Could not get installed packages: {0}".format(str(e)), exc_info=config.EXC_INFO)
    return packages


def _get_report_data(last_log_time: Optional[datetime] = None,
                     last_configuration: Optional[str] = None,
                     last_installed_packages: Optional[str] = None
                     ) -> Tuple[Dict[str, Any], Optional[datetime], str, str]:
    """
    Create the data to be sent to the motherships.

    Only logs newer than last_log_time are included, and the configuration and the installed
    packages are only included if they differ from what was last sent. The caller has to store
    the returned tracking values after a successful sending, so failed reports are retried with
    the complete data.

    :param last_log_time: The timestamp of the newest log already sent to this mothership.
    :param last_configuration: The serialized configuration last sent to this mothership.
    :param last_installed_packages: The serialized package list last sent to this mothership.
    :return: A tuple containing the report data, the timestamp of the newest included log
             (or last_log_time if no new logs exist), the serialized current configuration,
             and the serialized current package list.
    """
    mothership_data = {
        # Determine the status of the app (check if modules are configured).
        "status": "running" if len(data_layer.module_data) > 0 else "inactive",
        "version": data_layer.version,
        "description": os.environ.get("APP_DESCRIPTION", "-"),
        "allowed_commands": _allowed_commands()
    }

    # Only send the configuration if it changed since the last successful report.
    configuration = json.dumps(getattr(data_layer.configuration, "configuration_dict", []), default=str)
    if configuration != last_configuration:
        mothership_data["configuration"] = json.loads(configuration)

    # Same for the installed packages: the list is stable for the lifetime of an environment
    # and only changes when a module requirement gets installed, so resending it on every
    # heartbeat would be pure noise.
    # Dumped through __dict__ like the logs below - json.dumps would otherwise fall back to
    # default=str and serialize each dataclass as its repr rather than as an object.
    installed_packages = json.dumps([package.__dict__ for package in _get_installed_packages()], default=str)
    if installed_packages != last_installed_packages:
        mothership_data["installed_packages"] = json.loads(installed_packages)

    # Get the new logs (the ones not already sent to this mothership).
    simplified_logs = []
    newest_log_time = last_log_time
    for log in data_layer.latest_logs.copy():
        if last_log_time is not None and log.time <= last_log_time:
            continue
        # Create the simplified log data object.
        simplified_log = models.Log(level=log.fields.get("level"),
                                    message=log.fields.get("message"),
                                    module=log.fields.get("module"),
                                    name=log.fields.get("name"),
                                    time=log.time.isoformat())
        simplified_logs.append(simplified_log.__dict__)
        if newest_log_time is None or log.time > newest_log_time:
            newest_log_time = log.time

    mothership_data["latest_logs"] = simplified_logs
    mothership_data.update(metrics.metrics_registry.overall_performance())
    mothership_data.update(_get_system_stats())
    return mothership_data, newest_log_time, configuration, installed_packages


def process_tasks(task: dict[str, str | list]):
    """
    Process a task.

    :param task: The task to process.
    """
    command = task.get("command", None)
    # Caution: this guard used to read `if command not in [...] if ALLOWED_COMMANDS else []`,
    # which is a conditional expression, not a filtered comprehension. With ALLOWED_COMMANDS
    # unset it evaluated to `[]` - falsy - so the guard fell through and every remote command
    # was executed on an app that had granted none.
    if command not in _allowed_commands():
        logger.error("Received not permitted task with command: '{0}'. "
                     "Add it to 'allowed_commands' in your {1} to permit it."
                     .format(command, config.SETTINGS_FILENAME))
        return

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
                logger.info("Successfully updated git_access_token.txt file with your git token.")
                file.write(git_access_token)
        utils.updater.update_app()
    elif command == "load":
        errors = data_layer.configuration.load_configuration_from_stream(
            content=json.dumps(task.get("configuration")))
        if errors:
            logger.error(
                "The following errors occurred while trying to deserialize the configuration:\n" +
                "\n".join("{}: {}".format(k, v) for k, v in errors.items()))
    elif command == "save":
        success, error = data_layer.configuration.save_configuration_as_file(
            content=json.dumps(task.get("configuration")))
        if not success:
            logger.error("Could not save file: {0}".format(error))
    else:
        logger.error("Received task with unknown command: '{0}'.".format(command))


def _sleep_remaining(cycle_start: float, interval: int):
    """
    Sleep for whatever is left of the interval since the cycle started.

    Paced with time.monotonic() rather than datetime.now(): wall time can jump backwards
    (an NTP correction, or DST on a naive local clock), and timedelta.seconds turns such a
    negative difference into ~86399. That is never below the interval, so the sleep was
    skipped and the loop span at full request rate until the clock caught up.

    :param cycle_start: The monotonic timestamp taken at the start of the cycle.
    :param interval: The desired number of seconds between two cycle starts.
    """
    elapsed = time.monotonic() - cycle_start
    if elapsed < interval:
        time.sleep(interval - elapsed)


def _hub_login(session: requests.Session, log_times: Dict[str, datetime], address: str) -> bool:
    """
    Authenticate a session against the hub using the configured api access token.

    :param session: The session to set the authorization header on.
    :param log_times: The error log registry used to throttle repeated failures.
    :param address: The hub address this session talks to, for the log message.
    :return: True if the token was accepted.
    """
    try:
        session.headers = {"Accept": "application/json",
                           "Content-Type": "application/json",
                           "Authorization": f"Bearer {os.environ.get('HUB_API_ACCESS_TOKEN')}"}
        # Test the token.
        response = session.post(url=config.HUB_TEST_TOKEN_ADDRESS,
                                timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
        response.raise_for_status()
        return True
    except Exception as e:
        _log_error_throttled(log_times, address + "_login",
                             "Invalid api access token for requesting tasks on {0}: {1}. "
                             "Please check or create an api access token on your hub profile. "
                             "You can also turn off the reporting functionality ('report_to_hub') "
                             "in your settings.ini.".format(address, str(e)))
        return False


def _report_hub():
    """
    Sends post request containing current app data cyclically to the hub.
    This function is called in a separate thread.
    """
    logged_in = False
    session = utils.resilient_session.create_resilient_session()
    last_log_time: Optional[datetime] = None
    last_configuration: Optional[str] = None
    last_installed_packages: Optional[str] = None

    while data_layer.running:
        cycle_start = time.monotonic()

        if not logged_in:
            logged_in = _hub_login(session, data_layer.last_mothership_sending_error_log, config.HUB_APP_ADDRESS)
        if logged_in:
            try:
                json_data, newest_log_time, sent_configuration, sent_installed_packages = _get_report_data(
                    last_log_time, last_configuration, last_installed_packages)
                json_data["app_id"] = os.environ.get("APP_ID")
                response = session.post(url=f"{config.HUB_APP_ADDRESS}",
                                        timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT),
                                        json=json.loads(json.dumps(json_data, default=str)))
                response.raise_for_status()
                # Only remember what was sent after a successful report, so failures are retried.
                last_log_time = newest_log_time
                last_configuration = sent_configuration
                last_installed_packages = sent_installed_packages
            except Exception as e:
                logged_in = False
                _log_error_throttled(data_layer.last_mothership_sending_error_log, config.HUB_APP_ADDRESS,
                                     "Could not send report to mothership '{0}': {1}"
                                     .format(config.HUB_APP_ADDRESS, str(e)))

        _sleep_remaining(cycle_start, config.REPORT_INTERVAL)


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
    session = utils.resilient_session.create_resilient_session()
    logged_in = False

    while data_layer.running:
        cycle_start = time.monotonic()

        if not logged_in:
            logged_in = _hub_login(session, data_layer.last_mothership_receiving_error_log, config.HUB_TASK_ADDRESS)
        if logged_in:
            try:
                response = session.get(url=f'{config.HUB_TASK_ADDRESS}/{os.environ.get("APP_ID")}',
                                       timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
                response.raise_for_status()
                json_response = response.json()
                for task in json_response:
                    logger.info("Received task '{0}' from hub '{1}'."
                                .format(task.get("command", "-"), config.HUB_APP_ADDRESS))
                    if config.VERIFY_TASK_SIGNATURE:
                        if utils.security.verify_task_signature(task=task):
                            process_tasks(task)
                        else:
                            logger.critical("Task signature verification failed for task '{0}' with the command '{1}'."
                                            .format(task.get("id", "-"), task.get("command", "-")))
                    else:
                        process_tasks(task)
            except Exception as e:
                logged_in = False
                _log_error_throttled(data_layer.last_mothership_receiving_error_log, config.HUB_TASK_ADDRESS,
                                     "Could not request or process task from hub '{0}': {1}"
                                     .format(config.HUB_APP_ADDRESS, str(e)))

        _sleep_remaining(cycle_start, config.REQUEST_INTERVAL)


def _report(mothership: str):
    """
    Sends post request containing current app data cyclically to the mothership.
    This function is called in a separate thread.

    :param mothership: The mothership address.
    """
    session = utils.resilient_session.create_resilient_session()
    session.headers.update({'Accept': 'application/json', 'Content-Type': 'application/json'})
    last_log_time: Optional[datetime] = None
    last_configuration: Optional[str] = None
    last_installed_packages: Optional[str] = None

    while data_layer.running:
        cycle_start = time.monotonic()

        try:
            json_data, newest_log_time, sent_configuration, sent_installed_packages = _get_report_data(
                last_log_time, last_configuration, last_installed_packages)
            json_data["app_id"] = os.environ.get("APP_ID")
            response = session.post(url=f"{mothership}/api/v1/app",
                                    timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT),
                                    json=json_data)
            response.raise_for_status()
            # Only remember what was sent after a successful report, so failures are retried.
            last_log_time = newest_log_time
            last_configuration = sent_configuration
            last_installed_packages = sent_installed_packages
        except Exception as e:
            _log_error_throttled(data_layer.last_mothership_sending_error_log, mothership,
                                 "Could not send report to mothership '{0}': {1}".format(mothership, str(e)))

        _sleep_remaining(cycle_start, config.REPORT_INTERVAL)


def _request_tasks(mothership):
    """
    Send get request (requesting new todos) cyclically to the mothership.

    The requested json body can contain the following commands:

    {
    "command": "restart, start, save, stop, load, or update",
    "configuration": [json_config]  # If 'load' or 'save' is the command.
    "git_access_token": str  # if 'update' is the command. Is optional!
    }

    :param mothership: The mothership address.
    """
    session = utils.resilient_session.create_resilient_session()
    session.headers.update({'Accept': 'application/json', 'Content-Type': 'application/json'})

    while data_layer.running:
        cycle_start = time.monotonic()

        try:
            # `/task/app_id/{app_id}`, matching the hub — see HUB_TASK_ADDRESS above,
            # which has always addressed tasks this way. The two are now spelled the
            # same, so a mothership is a mothership whether it is the hub or a peer.
            response = session.get(url=f"{mothership}/api/v1/task/app_id/{os.environ.get('APP_ID')}",
                                   timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT),
                                   headers={'Accept': 'application/json', 'Content-Type': 'application/json'})
            response.raise_for_status()
            json_response = response.json()
            for task in json_response:
                logger.info("Received task '{0}' from mothership '{1}'."
                            .format(task.get("command", "No command given..."), mothership))
                process_tasks(task)
        except Exception as e:
            _log_error_throttled(data_layer.last_mothership_receiving_error_log, mothership,
                                 "Could not request or process todos from mothership '{0}': {1}"
                                 .format(mothership, str(e)))

        _sleep_remaining(cycle_start, config.REQUEST_INTERVAL)
