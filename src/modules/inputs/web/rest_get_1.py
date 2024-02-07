"""
If the json response contains just a list of values (of type: bool, int, float, or str)
a field with the key `list` is added.
"""
from dataclasses import dataclass, field
from threading import Thread
from typing import Dict, Any, List, Optional
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
__description__: str = "This module sends REST GET requests to a given endpoint and forwards the received response."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = []
"""Define your requirements here."""


def _extract_values(obj, keys: List[str]) -> dict:
    """
    Pull all values of a specified key from nested JSON.

    :param obj: The json object.
    :param keys: The keys which are searched.

    :returns: Returns a list with the found values for the key.
    """
    fields: Dict[str, Any] = {}
    calls: int = 0
    """The number of calls of the recursive function _extract."""

    def _extract(obj, fields, keys, calls):
        """
        Recursively search for values of key in JSON tree.
        """
        calls += 1
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict):
                    # Directly add if the user wants to.
                    if k in keys:
                        fields[k] = v
                    else:
                        _extract(v, fields, keys, calls)
                elif isinstance(v, list):
                    if k in keys:
                        # Directly add, if the user wants to.
                        fields[k] = v
                    elif any(isinstance(value, (dict, list)) for value in v):
                        _extract(v, fields, keys, calls)
                    elif not keys:
                        fields[k] = v
                elif k in keys or not keys:
                    fields[k] = v
        elif isinstance(obj, list):
            # Check if it is just a list.
            if all([isinstance(elem, (int, float, bool, str)) for elem in obj]) and calls == 1:
                fields["list"] = obj
            else:
                for item in obj:
                    _extract(item, fields, keys, calls)

        return fields

    fields = _extract(obj, fields, keys, calls)

    return fields


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
        response.raise_for_status()
        json_response = response.json()

        keys = []
        # Search for the keys in the response json.
        for key in self.configuration.keys:
            # Replace the dynamic variables.
            try:
                keys.append(self._dyn(key))
            except Exception as e:
                self.logger.error("{0}".format(str(e)))

        return _extract_values(json_response, keys)

    except DynamicVariableException as e:
        self.logger.error("Could not replace dynamic variable. {0}"
                          .format(str(e)), exc_info=config.EXC_INFO)
        return None
    except Exception as e:
        self.logger.error("An unexpected error occurred. Request was not successful: {0}"
                          .format(str(e)), exc_info=config.EXC_INFO)
        return None


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
    description: str = "This module sends a HTTP REST request in a defined interval and forwards the received response."
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
                                      "module_name: inputs.web.rest_get_1",
                          required=True),
            default=None)
        keys: List[str] = field(
            metadata=dict(description="The keys in the received json response to be extracted. "
                                      "If no keys are given, all keys are extracted.",
                          required=False,
                          dynamic=True),
            default_factory=list)
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
            default=10)
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
        only_forward_on_change: bool = field(
            metadata=dict(description="Only forward the data object if the field values have changed.",
                          required=False,
                          dynamic=False),
            default=True)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

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
        This method creates a new loop requesting the endpoint in the given interval.
        """
        # The start time of the execution. Needed for the try to implement a non-shifting execution routine.
        start_time = datetime.datetime.now()
        previous = None
        while self.active and self.input_module_instance.session:
            try:
                fields = _request(self)
                # Check if the data changed.
                if self.configuration.only_forward_on_change:
                    if previous != fields and fields is not None:
                        previous = fields
                        data = models.Data(measurement=self.configuration.measurement, fields=fields)
                        self._data_change(data)
                elif fields is not None:
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
    description: str = "This module sends a HTTP REST request if requested and forwards the received response."
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
                                      "module_name: inputs.web.rest_get_1",
                          required=True),
            default=None)
        keys: List[str] = field(
            metadata=dict(description="The keys in the received json response to be extracted.",
                          required=True,
                          dynamic=True),
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
            default=10)
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

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        fields = _request(self)
        return fields if fields is not None else {}
