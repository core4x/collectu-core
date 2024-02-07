"""
The request result is added with the key `status`.
Values can be `1` (service is running - no timeout) or `-1` service undefined (timed out).
If `consider_previous_status` is true, and was previously once `1` and now times out, the status will be `2`.

If `consider_response_code` is true, the response has to be 200. Otherwise,
the status (if no timeout -> `-1`) will be `2`.

Summarized:
- `-1`: The request timed out.
- `1`:  No time out (and if `consider_response_code` is true, response code was 200).
- `2`:  If `consider_previous_status` is true, status changed from `1` to time out,
        or if `consider_response_code` is true, response code was not 200.
"""
from dataclasses import dataclass, field
from threading import Thread
from typing import Dict, Any, Optional
import time
import datetime

# Internal imports.
import config
from models.validations import Range
from modules.base.base import DynamicVariableException
from modules.base.base import send_data
from modules.inputs.base.base import AbstractInputModule, AbstractVariableModule, AbstractTagModule, models

# Third party imports.
import requests

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = True
"""Is this module public?"""
__description__: str = "This module sends a HTTP GET request to a given endpoint and checks if the request times out " \
                       "and optionally the status code."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = []
"""Define your requirements here."""


def _request(self) -> Optional[dict]:
    """
    This method makes a get request to the given variable and returns the received and extracted values.

    :param self: The instance requesting the variables.
    :returns: Returns the received and extracted fields.
    """
    try:
        # Get all headers from the configuration.
        headers = {}
        for key, value in self.configuration.headers.items():
            try:
                headers[self._dyn(key)] = self._dyn(value)
            except LookupError as e:
                self.logger.warning("Could not set header '{0}: {1}': {2}".format(key, value, str(e)))

        # Get all params from the configuration.
        params = {}
        for key, value in self.configuration.parameters.items():
            try:
                params[self._dyn(key)] = self._dyn(value)
            except LookupError as e:
                self.logger.warning("Could not set parameter '{0}: {1}': {2}".format(key, value, str(e)))

        # Update the session params and headers.
        self.input_module_instance.session.params.update(params)
        self.input_module_instance.session.headers.update(headers)

        url = f"{self._dyn(self.configuration.host)}:{self._dyn(self.configuration.port, 'int')}{self._dyn(self._dyn(self.configuration.path))}"

        # Send the actual request.
        response = self.input_module_instance.session.get(url=url,
                                                          timeout=(self.configuration.timeout,
                                                                   self.configuration.timeout))

        if self.configuration.consider_response_code and response.status_code != 200:
            return {"status": 2}

        # Everything was fine.
        self.previous_status[url] = 1
        return {"status": 1}

    except DynamicVariableException as e:
        self.logger.error("Could not replace dynamic variable. {0}"
                          .format(str(e)), exc_info=config.EXC_INFO)
        return None
    except Exception as e:
        # Request timed out.
        if self.configuration.consider_previous_status and self.previous_status.get(url, 0) == 1:
            return {"status": 2}
        else:
            return {"status": -1}


class InputModule(AbstractInputModule):
    """
    Class for the input module.

    :param configuration: The configuration object of the module.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module creates a session pool for HTTP requests. " \
                       "This is the base and required for the according variable and tag modules."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.InputModule):
        """
        The configuration model of the module.
        """
        anonymous: bool = field(
            metadata=dict(description="Is authentication required.",
                          required=False),
            default=True)
        username: str = field(
            metadata=dict(description="The username for the basic authentication.",
                          required=False),
            default='admin')
        password: str = field(
            metadata=dict(description="The password for the basic authentication.",
                          required=False),
            default='admin')

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.session = None
        """Session connection pool."""

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            self.session = requests.Session()

            # Basic authentication.
            login = None
            if not self.configuration.anonymous:
                login = (self.configuration.username,
                         self.configuration.password)
            self.session.auth = login
            return True
        except Exception as e:
            self.logger.critical("Could not create session: {0}"
                                 .format(str(e)), exc_info=config.EXC_INFO)
            return False

    def stop(self):
        """
        Method for stopping the module. Is called by the main thread.
        """
        self.session.close()


class VariableModule(AbstractVariableModule):
    """
    A variable module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module sends a HTTP GET request in a defined interval to a given endpoint and checks if " \
                       "the request times out and optionally the status code."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        input_module: str = field(
            metadata=dict(description="The id of the input module. The required input module has to be "
                                      "module_name: inputs.web.rest_status_1",
                          required=True),
            default=None)
        path: str = field(
            metadata=dict(description="The path to the endpoint (e.g. `/path`) including `/`.",
                          required=True,
                          dynamic=True),
            default=None)
        host: str = field(
            metadata=dict(description="The host address of the server.",
                          required=False,
                          dynamic=True),
            default="http://127.0.0.1")
        port: int = field(
            metadata=dict(description="The port of the server.",
                          required=False,
                          dynamic=True),
            default=80)
        interval: float = field(
            metadata=dict(description="Interval in seconds in which the endpoint is requested "
                                      "and subsequently checked for changes.",
                          required=False,
                          validate=Range(min=0, max=1000)),
            default=10)
        timeout: float = field(
            metadata=dict(description="The [connect and read timeout]"
                                      "(https://requests.readthedocs.io/en/master/user/advanced/#timeouts) in seconds.",
                          required=False,
                          validate=Range(min=0, max=100)),
            default=9)
        headers: Dict[str, str] = field(
            metadata=dict(description="HTTP headers send with the request. Can be used for authentication.",
                          required=False,
                          dynamic=True),
            default_factory=lambda: {'Accept': 'application/json', 'Cache-Control': 'no-cache'})
        parameters: Dict[str, str] = field(
            metadata=dict(description="HTTP parameters send with the request.",
                          required=False,
                          dynamic=True),
            default_factory=dict)
        consider_response_code: bool = field(
            metadata=dict(description="Consider the response code of the request. "
                                      "If the response is not 200, the status will be error (`2`) or undefined (`-1`).",
                          required=False,
                          dynamic=False),
            default=True)
        consider_previous_status: bool = field(
            metadata=dict(description="Consider the previous status of the request to the `host:port+path`. "
                                      "If the service was previously once `1`, "
                                      "and now times out, the status will be `2`.",
                          required=False,
                          dynamic=False),
            default=True)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        self.previous_status: Dict[str, int] = {}
        """The previous status of the request to `host:port+path`."""

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.

        :returns: True if successfully started, otherwise false.
        """
        Thread(target=self._subscribe,
               daemon=False,
               name="REST_Get_Variable_Module_Loop_{0}".format(self.configuration.id)).start()
        return True

    def _subscribe(self):
        """
        This method creates a new loop requesting the endpoint in the given interval
        """
        # The start time of the execution. Needed for the try to implement a non-shifting execution routine.
        start_time = datetime.datetime.now()
        while self.active and self.input_module_instance.session:
            try:
                fields = _request(self)
                if fields is not None:
                    data = models.Data(measurement=self.configuration.measurement, fields=fields)
                    self._data_change(data)
                # This should prevent shifting a little.
                required_time = datetime.datetime.now() - start_time
                if self.configuration.interval > float(required_time.seconds):
                    time.sleep(self.configuration.interval - float(required_time.seconds))
                else:
                    self.logger.warning("The interval '{0}' s is to short for the request. "
                                        "The required time is '{1}' s."
                                        .format(str(self.configuration.interval), str(required_time)))
                start_time = datetime.datetime.now()
            except Exception as e:
                self.logger.error("Something unexpected went wrong while requesting: {0}"
                                  .format(str(e)), exc_info=config.EXC_INFO)

    @send_data
    def _data_change(self, data: models.Data):
        """
        Send the data.
        """
        return data


class TagModule(AbstractTagModule):
    """
    A tag module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module sends a HTTP GET request if requested to a given endpoint and checks if " \
                       "the request times out and optionally the status code."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.TagModule):
        """
        The configuration model of the module.
        """
        input_module: str = field(
            metadata=dict(description="The id of the input module. The required input module has to be "
                                      "module_name: inputs.web.rest_status_1",
                          required=True),
            default=None)
        path: str = field(
            metadata=dict(description="The path to the endpoint (e.g. `/path`) including `/`.",
                          required=True,
                          dynamic=True),
            default=None)
        host: str = field(
            metadata=dict(description="The host address of the server.",
                          required=False,
                          dynamic=True),
            default="http://127.0.0.1")
        port: int = field(
            metadata=dict(description="The port of the server.",
                          required=False,
                          dynamic=True),
            default=80)
        timeout: float = field(
            metadata=dict(description="The [connect and read timeout]"
                                      "(https://requests.readthedocs.io/en/master/user/advanced/#timeouts) in seconds.",
                          required=False,
                          validate=Range(min=0, max=100)),
            default=9)
        headers: Dict[str, str] = field(
            metadata=dict(description="HTTP headers send with the request. Can be used for authentication.",
                          required=False,
                          dynamic=True),
            default_factory=lambda: {'Accept': 'application/json', 'Cache-Control': 'no-cache'})
        parameters: Dict[str, str] = field(
            metadata=dict(description="HTTP parameters send with the request.",
                          required=False,
                          dynamic=True),
            default_factory=dict)
        consider_response_code: bool = field(
            metadata=dict(description="Consider the response code of the request. "
                                      "If the response is not 200, the status will be error (`2`) or undefined (`-1`).",
                          required=False,
                          dynamic=False),
            default=True)
        consider_previous_status: bool = field(
            metadata=dict(description="Consider the previous status of the request to the `host:port+path`. "
                                      "If the service was previously `1` and now times out, the status will be `2`.",
                          required=False,
                          dynamic=False),
            default=True)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        self.previous_status: Dict[str, int] = {}
        """The previous status of the request to `host:port+path`."""

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        fields = _request(self)
        return fields if fields is not None else {}
