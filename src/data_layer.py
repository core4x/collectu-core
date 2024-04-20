"""
The data layer holds all global data objects of the main process.
"""
from typing import Any, Deque, Optional
import collections
import datetime
import multiprocessing

# Internal imports.
import config
from configuration import Configuration
import models
import utils.usage_statistics

# CAUTION!!!
# The following objects are only accessible by the main process!!!
# If you want to access data from another process, you have to use the multiprocessing objects
# (e.g. managers) defined in main.py (see below).

version: str = "unknown"
"""The version of the application."""

running = True
"""A flag which is set to false, if the app has to be stopped."""

settings: dict[str, str] = {}
"""The loaded content of the settings.ini file or environment variables set in another way. 
If these settings are changed, you have to call utils.initialization.update_env_variables. 
However, some environment variables are only loaded during start-up. So, better restart the complete app."""

registered_modules: dict[str, Any] = {}
"""All available modules with the module name as key."""

configuration: Optional[Configuration] = None
"""The configuration class."""

module_data: dict[str, models.ModuleData] = {}
"""Dictionary containing all configured modules and additional information with the module id as key."""

buffer_instance = None
"""The instantiated buffer output module."""

dashboard_modules: list[Any] = []
"""List of processor visualization instances. Processors register them self here."""

mothership_data: dict[str, models.MothershipData] = {}
"""The received mothership data with the app_id as key."""

statistics: Optional[utils.usage_statistics.Statistics] = None
"""The usage statistic sender if SEND_USAGE_STATISTICS is enabled."""

latest_logs: Deque[models.Data] = collections.deque(maxlen=config.NUMBER_OF_BUFFERED_LOGS)
"""Deque containing the latest (maxlen) captured logs."""

last_mothership_sending_error_log: dict[str, datetime.datetime] = {}
"""A dictionary with the receiving address as key and the timestamp as value of the last error logging 
if the sending process to the mothership api failed."""

last_mothership_receiving_error_log: dict[str, datetime.datetime] = {}
"""A dictionary with the receiving address as key and the timestamp as value of the last error logging 
if the task receiving process failed."""

last_statistics_sending_error_log: Optional[datetime.datetime] = None
"""The timestamp of the last error logging if the sending process to the statistics api failed."""
