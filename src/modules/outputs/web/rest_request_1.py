"""
**Note:**   The Rest request output module is comparatively slow. If you have fast changing variables,
use another output module.

When the Rest request output module is added to the configuration,
the data changes are saved in the following way in the body of the request (if `custom_data` is not set):

```json
{
  "measurement": "measurement",
  "tags": {"level": "INFO", "module": "excel_output_module"},
  "time": "2020-11-27 09:58:23.017578",
  "fields": {"level": "INFO", "module": "excel_output_module"}
}
```

If a field with the name `file` is given, we convert it to a file object and send it with the request.
If a `file` is defined, we also need a key with `filename` as string.
Only available for POST and PUT.
"""
from threading import Thread
from dataclasses import dataclass, field
import json
from typing import Dict, Any
import io

# Internal imports.
import config
from modules.outputs.base.base import AbstractOutputModule, models
from models.validations import OneOf

# Third party requirements.
import requests


class OutputModule(AbstractOutputModule):
    """
    Class for the console output module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module sends a RESTful HTTP request containing the data as json."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    can_be_buffer: bool = False
    """If True, the child has to implement 'store_buffer_data' and 'get_buffer_data'."""

    @dataclass
    class Configuration(models.OutputModule):
        """
        The configuration model of the module.
        """
        path: str = field(
            metadata=dict(description="The path to the endpoint (e.g. `/post`) including `/`.",
                          required=False,
                          dynamic=True),
            default="/post")
        host: str = field(
            metadata=dict(description="The host address of the endpoint.",
                          required=False,
                          dynamic=True),
            default="https://httpbin.org")
        port: int = field(
            metadata=dict(description="The port of the endpoint.",
                          required=False,
                          dynamic=True),
            default=443)
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
        custom_data: Dict[str, Any] = field(
            metadata=dict(description="If custom data is set, only this is send. Only values can be dynamic.",
                          required=False,
                          dynamic=True),
            default_factory=dict)
        method: str = field(
            metadata=dict(description="The method of the request.",
                          required=False,
                          validate=OneOf(possibilities=["POST", "PUT", "DELETE"])),
            default='POST')

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
        super().__init__(configuration=configuration)
        self.session = None
        """The session to the receiver."""

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {"method": ["POST", "PUT", "DELETE"]}

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            self.session = requests.Session()
            login = None
            if not self.configuration.anonymous:
                login = (self.configuration.username,
                         self.configuration.password)
            self.session.auth = login
            # Start the queue processing for storing incoming data.
            Thread(target=self._process_queue,
                   daemon=False,
                   name="Queue_Worker_{0}".format(self.configuration.id)).start()

            self.logger.info("Successfully initialized for endpoint '{0}'."
                             .format(self.configuration.host + ":" + str(self.configuration.port) +
                                     self.configuration.path))
            return True

        except Exception as e:
            self.logger.critical("Something went wrong while trying to establish connection to '{0}{1}': {2}"
                                 .format(self.configuration.host + ":" + str(self.configuration.port),
                                         self.configuration.path, str(e)),
                                 exc_info=config.EXC_INFO)
            return False

    def stop(self):
        """
        Method for stopping the output module. Is called by the main thread.
        """
        self.session.close()

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        try:
            # Check if a file is given.
            file = None
            if data.fields.get("file", False) and \
                    data.fields.get("filename", False) and \
                    self.configuration.method.upper() != "DELETE":
                # A file and filename is given.
                # Make a data object from it.
                file = io.StringIO(data.fields.get("file"))
                file.name = data.fields.get("filename")

            if self.configuration.custom_data:
                if isinstance(self.configuration.custom_data, dict):
                    json_data = {}
                    for key, value in self.configuration.custom_data.items():
                        json_data[key] = self._dyn(value)
                elif isinstance(self.configuration.custom_data, list):
                    json_data = []
                    for index, element in enumerate(self.configuration.custom_data):
                        json_data.append(self._dyn(element))
                else:
                    raise Exception("Unknown type '{0}' of custom data is given. "
                                    "Custom data should be a list or dict."
                                    .format(type(self.configuration.custom_data)))
            else:
                # Remove the file entries.
                if "file" in data.fields.keys():
                    data.fields.pop("file")
                if "filename" in data.fields.keys():
                    data.fields.pop("filename")
                json_data = json.dumps(data.__dict__, default=str)

            headers = {}
            params = {}

            # Get all headers from the configuration.
            for key, value in self.configuration.headers.items():
                try:
                    headers[self._dyn(key)] = self._dyn(value)
                except LookupError as e:
                    self.logger.warning("Could not set header '{0}: {1}': {2}".format(key, value, str(e)))

            # Get all params from the configuration.
            for key, value in self.configuration.parameters.items():
                try:
                    params[self._dyn(key)] = self._dyn(value)
                except LookupError as e:
                    self.logger.warning("Could not set parameter '{0}: {1}': {2}".format(key, value, str(e)))

            self.session.params.update(params)
            self.session.headers.update(headers)

            url = f"{self._dyn(self.configuration.host)}:{self._dyn(self.configuration.port, 'int')}{self._dyn(self.configuration.path)}"

            if self.configuration.method.upper() == "POST":
                if file:
                    response = self.session.post(url=url,
                                                 timeout=(10, 10),
                                                 json=json_data,
                                                 files={'file': file})
                else:
                    response = self.session.post(url=url,
                                                 timeout=(10, 10),
                                                 json=json_data)
            elif self.configuration.method.upper() == "PUT":
                if file:
                    response = self.session.put(url=url,
                                                timeout=(10, 10),
                                                json=json_data,
                                                files={'file': file})
                else:
                    response = self.session.put(url=url,
                                                timeout=(10, 10),
                                                json=json_data)
            else:
                # Should always be delete.
                response = self.session.delete(url=url,
                                               timeout=(10, 10),
                                               json=json_data)
            response.raise_for_status()

        except LookupError as e:
            self.logger.error("Could not replace dynamic variable. {0}"
                              .format(str(e)),
                              exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
        except (requests.exceptions.HTTPError, ConnectionError, requests.exceptions.Timeout) as e:
            self.logger.error("An error occurred. Trying to buffer the data. {0}"
                              .format(str(e)),
                              exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=False)
        except Exception as e:
            self.logger.error("Something went wrong while trying to store data. {0}"
                              .format(str(e)),
                              exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
