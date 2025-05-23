"""
The config file holds all global constants.
"""
from typing import Optional

APP_NAME: str = "Collectu"
"""The application name."""

CONTACT: str = "info@collectu.de"
"""The e-mail address of the creator."""

SETTINGS_FILENAME: str = "settings.ini"
"""The filename of the settings file containing the environment variables to be set."""

DEBUG: bool = False
"""Debug messages are printed into the console."""

EXC_INFO: bool = False
"""Traceback of exceptions are printed."""

NUMBER_OF_BUFFERED_LOGS: int = 50
"""The number of buffered logs."""

AUTOSAVE_NUMBER: int = 10
"""The number of autosave entries in the configuration database."""

RETRY_INTERVAL: Optional[int] = 10
"""The sleep time in seconds between retry attempts to start a module. If 'None', it is directly retried."""

WARNING_LIMIT: int = 1000
"""Print a warning log message, as soon as we have more then warning_limit elements in the queue of an output module."""

STOP_LIMIT: int = 10000
"""Do not store elements in the queue of an output module as long as there are more elements then STOP_LIMIT."""

REPORT_INTERVAL: int = 3
"""The interval in seconds for sending the app info to the mothership and the statistics endpoint."""

REPORTER_TIMEOUT: int = 9
"""The time in seconds, when we will reset the db entry of a reporter to unknown."""

REQUEST_INTERVAL: int = 3
"""The interval in seconds for requesting todos from the mothership."""

USAGE_STATISTICS_RECEIVER: str = "https://api.collectu.de/api/v1/statistic"
"""The receiver address where the usage statistic is send to. Used in utils.usage_statistics."""

HUB_ADDRESS: str = "https://api.collectu.de/api/v1"
"""The base address of the api."""

HUB_MODULES_ADDRESS: str = "https://api.collectu.de/api/v1/module"
"""The endpoint of the api for registering modules."""

HUB_CONFIGURATIONS_ADDRESS: str = "https://api.collectu.de/api/v1/configuration"
"""The endpoint of the api for registering configurations."""

HUB_APP_ADDRESS: str = "https://api.collectu.de/api/v1/app"
"""The endpoint of the api for reporting app data. Used in utils.mothership_interface."""

HUB_GET_APP_ADDRESS: str = "https://api.collectu.de/api/v1/app/app_id"
"""The endpoint of the api for getting app data. Used for api authentication."""

HUB_TASK_ADDRESS: str = "https://api.collectu.de/api/v1/task/app_id"
"""The endpoint of the api for requesting tasks. Used in utils.mothership_interface."""

HUB_TEST_TOKEN_ADDRESS: str = "https://api.collectu.de/api/v1/login/test-token"
"""The endpoint of the api for testing the api access token."""

HUB_LOGIN_ADDRESS: str = "https://api.collectu.de/api/v1/login/access-token"
"""The endpoint of the api for logging in."""

STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL: int = 10
"""The interval in seconds in which error messages are logged 
if the sending or receiving process with the external api fails."""

CHECK_VALUE: str = "jkhdegkjhedlkl"
"""A check value."""

STOP_TIMEOUT: int = 3
"""The timeout in seconds to stop all modules."""
