"""
Functions for sending usage statistics.
"""
import os
import json
import logging
import time
from threading import Thread

# Internal imports.
import config
import data_layer

# Third party imports.
import requests

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


class Statistics:
    """
    A class for sending statistics about the app usage.
    """

    def __init__(self):
        self.session = requests.Session()
        """The session for sending the data."""
        self.session.headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        Thread(target=self._send,
               daemon=True,
               name="Statistics").start()
        logger.info(f"Started sending usage statistics to {config.USAGE_STATISTICS_RECEIVER}.")

    def _send(self):
        """
        Sends the data to the statistics receiver.
        """
        while data_layer.running:
            try:
                response = self.session.post(url=config.USAGE_STATISTICS_RECEIVER,
                                             # verify=False,  # Disable SSL verification.
                                             data=json.dumps({
                                                 "version": data_layer.version,
                                                 "app_id": os.environ.get("APP_ID"),
                                                 "app_description": os.environ.get("APP_DESCRIPTION", "-"),
                                                 "running_modules_count": len(data_layer.module_data.keys())},
                                                 default=str),
                                             allow_redirects=True,
                                             timeout=(3, 3))
                response.raise_for_status()
            except Exception as e:
                logger.error("Something unexpected went wrong while trying to send usage statistics: {0}"
                             .format(str(e)), exc_info=config.EXC_INFO)
            finally:
                time.sleep(config.REPORT_INTERVAL)
