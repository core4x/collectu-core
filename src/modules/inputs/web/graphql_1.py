"""
Only if the received data has changed, it is forwarded.

#### Technical Debts

*   The GraphQL input module can not handle list values: `"cars": ["Ford", "BMW", "Fiat"]`.
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
__description__: str = "This module sends a HTTP post request containing a query to a given GraphQL endpoint."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = []
"""Define your requirements here."""


def _extract_values(obj, key: str) -> list:
    """
    Pull all values of a specified key from nested JSON.

    :param obj: The json object.
    :param key: The key which is searched.

    :returns: Returns a list with the found values for the key.
    """
    arr = []

    def _extract(obj, arr, key):
        """
        Recursively search for values of key in JSON tree.
        """
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    _extract(v, arr, key)
                elif k == key:
                    arr.append(v)
        elif isinstance(obj, list):
            for item in obj:
                _extract(item, arr, key)
        return arr

    results = _extract(obj, arr, key)
    return results


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

        url = f"{self._dyn(self.configuration.host)}:{self._dyn(self.configuration.port, 'int')}"

        # Send the actual request.
        response = self.input_module_instance.session.post(url=url,
                                                           timeout=(self.configuration.timeout,
                                                                    self.configuration.timeout),
                                                           json={'query': self._dyn(self.configuration.query)})
        response.raise_for_status()
        json_response = response.json()

        fields = {}
        # Search for the key in the response json.
        for key in self.configuration.keys:
            searched_key = self._dyn(key)
            field_value = _extract_values(json_response, searched_key)
            # If we found only a single value, we extract it from the list.
            if len(field_value) == 1:
                field_value = field_value[0]
            # Make a dictionary.
            fields[searched_key] = field_value

        return fields

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
    description: str = "This module creates a session pool for HTTP post requests. " \
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
    description: str = "This module sends a HTTP post request to an endpoint containing a query in a defined interval."
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
                                      "module_name: inputs.web.graphql_1",
                          required=True),
            default=None)
        query: str = field(
            metadata=dict(description="The graphQL query in json format send to the endpoint.",
                          required=True,
                          dynamic=True),
            default=None)
        keys: List[str] = field(
            metadata=dict(description="The keys in the received json response to be extracted.",
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
               name="GraphQL_Variable_Module_Loop_{0}".format(self.configuration.id)).start()
        return True

    def _subscribe(self):
        """
        This method creates a new loop requesting the endpoint in the given interval
        """
        # The start time of the execution. Needed for the try to implement a non-shifting execution routine.
        start_time = datetime.datetime.now()
        previous = None
        while self.active and self.input_module_instance.session:
            try:
                fields = _request(self)
                # Check if the data changed.
                if previous != fields and fields is not None:
                    previous = fields
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
    description: str = "This module sends a HTTP post request to an endpoint containing a query if requested."
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
                                      "module_name: inputs.web.graphql_1",
                          required=True),
            default=None)
        query: str = field(
            metadata=dict(description="The graphQL query in json format send to the endpoint.",
                          required=True,
                          dynamic=True),
            default=None)
        keys: List[str] = field(
            metadata=dict(description="The keys in the received json response to be extracted.",
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
