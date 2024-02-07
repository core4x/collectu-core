"""
Functions for sending usage statistics.
"""
import os
import socket
import logging
import collections
import time
import threading
import uuid
import json
import datetime

# Internal imports.
import config
import models
import data_layer

# Third party imports.
import requests

# from urllib3.exceptions import InsecureRequestWarning

# Suppress the insecure request (SSL) without verification (verify=False).
# Caution: The warning message is disabled system-wide.
# requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

LOG_LEVELS = {
    "info": 1,
    "warning": 2,
    "error": 3,
    "critical": 4
}

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def threaded(function):
    """
    Decorator to run the called function in a separate thread.
    """

    def run(*args, **kwargs):
        threading.Thread(target=function, args=args, kwargs=kwargs, daemon=True,
                         name="Usage_Statistics_Sender_{0}".format(uuid.uuid4())).start()

    return run


class Statistics:
    """
    A class for sending statistics about the app usage.

    :param send_logs: Send the latest recorded logs (errors and above).
    """

    def __init__(self, send_logs: bool = True):
        self.session = requests.Session()
        """The session for sending the data."""
        self.session.headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        self.log = True
        """Log error messages."""

        if send_logs:
            # Send every time we identify new logs.
            threading.Thread(target=self._send_logs,
                             daemon=True,
                             name="Usage_Statistics_Log_Sender").start()

        logger.info(f"Started sending usage statistics to {config.USAGE_STATISTICS_RECEIVER}.")

    @threaded
    def send_status(self):
        """
        Sends a notification, that the app is running. This method is called in main.py.
        """
        data: models.Data = models.Data(
            measurement="status",
            fields={"running": 1,
                    "version": config.VERSION,
                    "app_id": os.environ.get("APP_ID", "undefined"),
                    "app_name": config.APP_NAME,
                    "hostname": socket.gethostname(),
                    "running_modules_count": len(data_layer.module_data.keys()),
                    "git_access_token": os.environ.get("GIT_ACCESS_TOKEN", "undefined")},
            tags={"version": config.VERSION,
                  "app_id": os.environ.get("APP_ID", "undefined"),
                  "app_name": config.APP_NAME,
                  "hostname": socket.gethostname(),
                  "git_access_token": os.environ.get("GIT_ACCESS_TOKEN", "undefined")})
        self.send_data_to_statistics_receiver(data)

    def _send_logs(self):
        """
        Send the latest recorded logs (errors and above).
        """
        last_without_time = collections.deque(maxlen=10)
        """A collection containing the hash values of the last 10 logs."""
        last_send_logs = []
        """A list containing the last send log messages."""
        while data_layer.running:
            logs = data_layer.latest_logs.copy()
            for log in [log for log in logs if
                        log not in last_send_logs and
                        LOG_LEVELS.get(log.fields.get("level", "").lower(), 0) >= LOG_LEVELS.get("error", 1)]:
                # Prevent to flush the statistics receiver with log messages.
                # This is done by checking if the log message (only fields) already occurred more
                # than 2 times in the last 10 logs.
                hashed_fields = hash(tuple(sorted(log.fields.items())))
                if not last_without_time.count(hashed_fields) > 2:
                    # Overwrite the measurement name.
                    log.measurement = "logs"
                    log.tags["version"] = config.VERSION
                    log.tags["app_id"] = os.environ.get("APP_ID", "undefined")
                    log.tags["app_name"] = config.APP_NAME
                    log.tags["hostname"] = socket.gethostname()
                    log.fields["version"] = config.VERSION
                    log.fields["app_id"] = os.environ.get("APP_ID", "undefined")
                    log.fields["app_name"] = config.APP_NAME
                    log.fields["hostname"] = socket.gethostname()
                    self.send_data_to_statistics_receiver(log)
                last_without_time.append(hashed_fields)
            last_send_logs = logs
            # CAUTION: This sleep time is necessarily needed.
            # Otherwise, we block all other things (also when we are in a separate thread).
            # This causes for example, a very slow frontend.
            time.sleep(1)

    @threaded
    def send_invalid_update_attempt(self):
        """
        Sends a notification, that an invalid (no git access token) update attempt was made.
        """
        data: models.Data = models.Data(
            measurement="invalid_update_attempt",
            fields={"version": config.VERSION,
                    "app_id": os.environ.get("APP_ID", "undefined"),
                    "app_name": config.APP_NAME,
                    "hostname": socket.gethostname(),
                    "git_access_token": os.environ.get("GIT_ACCESS_TOKEN", "undefined")},
            tags={"version": config.VERSION,
                  "app_id": os.environ.get("APP_ID", "undefined"),
                  "app_name": config.APP_NAME,
                  "hostname": socket.gethostname(),
                  "git_access_token": os.environ.get("GIT_ACCESS_TOKEN", "undefined")})
        self.send_data_to_statistics_receiver(data)

    @threaded
    def send_successful_update(self):
        """
        Sends a notification, that a valid update was made.
        """
        data: models.Data = models.Data(
            measurement="valid_update",
            fields={"version": config.VERSION,
                    "app_id": os.environ.get("APP_ID", "undefined"),
                    "app_name": config.APP_NAME,
                    "hostname": socket.gethostname(),
                    "git_access_token": os.environ.get("GIT_ACCESS_TOKEN", "undefined")},
            tags={"version": config.VERSION,
                  "app_id": os.environ.get("APP_ID", "undefined"),
                  "app_name": config.APP_NAME,
                  "hostname": socket.gethostname(),
                  "git_access_token": os.environ.get("GIT_ACCESS_TOKEN", "undefined")})
        self.send_data_to_statistics_receiver(data)

    @threaded
    def send_data_to_statistics_receiver(self, data: models.Data):
        """
        Sends the data to the configured influxdb v1 endpoint.

        Note: Avoid using the following reserved keys: _field, _measurement, and time.
        If reserved keys are included as a tag or field key, the associated point is discarded.

        :param data: The data to be sent.
        """
        try:
            response = self.session.post(url=config.USAGE_STATISTICS_RECEIVER,
                                         # verify=False,  # Disable SSL verification.
                                         data=json.dumps(data.__dict__, default=str),
                                         allow_redirects=True)
            response.raise_for_status()
        except Exception as e:
            if data_layer.last_statistics_sending_error_log is None:
                self.log = True
            else:
                last_sending = datetime.datetime.now() - data_layer.last_statistics_sending_error_log
                if config.STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL < float(last_sending.seconds):
                    data_layer.last_statistics_sending_error_log = datetime.datetime.now()
                    self.log = True

            if self.log:
                self.log = False
                logger.error("Something unexpected went wrong while trying to send usage statistics: {0}"
                             .format(str(e)), exc_info=config.EXC_INFO)
