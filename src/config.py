"""
The config file holds all global constants.
"""
import os
from typing import Optional

APP_NAME: str = os.getenv("APP_NAME", "Collectu")
"""The application name."""

CONTACT: str = os.getenv("CONTACT", "info@collectu.de")
"""The e-mail address of the creator."""

SETTINGS_FILENAME: str = os.getenv("SETTINGS_FILENAME", "settings.ini")
"""The filename of the settings file containing the environment variables to be set."""

DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
"""Debug messages are printed into the console."""

EXC_INFO: bool = os.getenv("EXC_INFO", "False").lower() in ("true", "1", "yes")
"""Traceback of exceptions are printed."""

NUMBER_OF_BUFFERED_LOGS: int = int(os.getenv("NUMBER_OF_BUFFERED_LOGS", 50))
"""The number of buffered logs."""

AUTOSAVE_NUMBER: int = int(os.getenv("AUTOSAVE_NUMBER", 10))
"""The number of autosave entries in the configuration database."""

RETRY_INTERVAL: Optional[int] = int(os.getenv("RETRY_INTERVAL", 10))
"""The sleep time in seconds between retry attempts to start a module. If 'None', it is directly retried."""

WARNING_LIMIT: int = int(os.getenv("WARNING_LIMIT", 1000))
"""Print a warning log message, as soon as we have more than warning_limit elements in the queue of an output module."""

STOP_LIMIT: int = int(os.getenv("STOP_LIMIT", 10000))
"""Do not store elements in the queue of an output module as long as there are more elements than STOP_LIMIT."""

REPORT_INTERVAL: int = int(os.getenv("REPORT_INTERVAL", 3))
"""The interval in seconds for sending the app info to the mothership and the statistics endpoint."""

REPORTER_TIMEOUT: int = int(os.getenv("REPORTER_TIMEOUT", 9))
"""The time in seconds, when we will reset the db entry of a reporter to unknown."""

REQUEST_INTERVAL: int = int(os.getenv("REQUEST_INTERVAL", 3))
"""The interval in seconds for requesting todos from the mothership."""

HUB_ADDRESS: str = os.getenv("HUB_ADDRESS", "https://api.collectu.de/api/v1")
"""The base address of the api."""

USAGE_STATISTICS_RECEIVER: str = os.getenv("USAGE_STATISTICS_RECEIVER", f"{HUB_ADDRESS}/statistic")
"""The receiver address where the usage statistic is sent to. Used in utils.usage_statistics."""

HUB_MODULES_ADDRESS: str = os.getenv("HUB_MODULES_ADDRESS", f"{HUB_ADDRESS}/module")
"""The endpoint of the api for registering modules."""

HUB_CONFIGURATIONS_ADDRESS: str = os.getenv("HUB_CONFIGURATIONS_ADDRESS", f"{HUB_ADDRESS}/configuration")
"""The endpoint of the api for registering configurations."""

HUB_APP_ADDRESS: str = os.getenv("HUB_APP_ADDRESS", f"{HUB_ADDRESS}/app")
"""The endpoint of the api for reporting app data. Used in utils.mothership_interface."""

HUB_GET_APP_ADDRESS: str = os.getenv("HUB_GET_APP_ADDRESS", f"{HUB_ADDRESS}/app/app_id")
"""The endpoint of the api for getting app data. Used for api authentication."""

HUB_TASK_ADDRESS: str = os.getenv("HUB_TASK_ADDRESS", f"{HUB_ADDRESS}/task/app_id")
"""The endpoint of the api for requesting tasks. Used in utils.mothership_interface."""

HUB_TEST_TOKEN_ADDRESS: str = os.getenv("HUB_TEST_TOKEN_ADDRESS", f"{HUB_ADDRESS}/login/test-token")
"""The endpoint of the api for testing the api access token."""

HUB_LOGIN_ADDRESS: str = os.getenv("HUB_LOGIN_ADDRESS", f"{HUB_ADDRESS}/login/access-token")
"""The endpoint of the api for logging in."""

HUB_REFRESH_TOKEN_ADDRESS: str = os.getenv("HUB_LOGIN_ADDRESS", f"{HUB_ADDRESS}/login/refresh")
"""The endpoint of the api for refreshing token."""

HUB_LLM_DOCS_ADDRESS: str = os.getenv("HUB_LLM_DOCS_ADDRESS", "https://collectu.de/docs/llms.txt")
"""Sitemap for LLM friendly docs from Collectu."""

HUB_JWKS_URL: str = os.getenv("HUB_JWKS_URL", "https://api.collectu.de/.well-known/jwks.json")
"""The jwks url of the hub for validating signatures."""

VERIFY_TASK_SIGNATURE: bool = os.getenv("VERIFY_TASK_SIGNATURE", "True").lower() in ("true", "1", "yes")
"""Verify the task signature using the HUB_JWKS_URL."""

STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL: int = int(os.getenv("STATISTICS_AND_MOTHERSHIP_ERROR_LOGGING_INTERVAL", 10))
"""The interval in seconds in which error messages are logged if the sending or receiving process with the external api fails."""

ACCESS_TOKEN_EXPIRE_HOURS: float = os.environ.get('ACCESS_TOKEN_EXPIRE_HOURS', 0.25)
"""The time in hours after an access token expires."""

CHECK_VALUE: str = "jkhdegkjhedlkl"
"""A check value."""

STOP_TIMEOUT: int = int(os.getenv("STOP_TIMEOUT", 3))
"""The timeout in seconds to stop all modules."""

MCP_ALL_AS_TOOL: bool = os.getenv("MCP_ALL_AS_TOOL", "True").lower() in ("true", "1", "yes")
"""Currently, some LLMs only support tools (and not resources and resource_templates)."""
