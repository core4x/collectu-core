"""
**Note:**   The client has to send the client_key and authentication (if required)
            as json string in the first message after connection.
            The client_key is used to identify the according variable or tag module.

Example:

```json
{"client_key": "client1", "username": "admin", "password": "admin"}
```

**Note:**   When you want to use the TCP server input module inside docker,
            you have to specify the ports used in the configuration file also inside `docker-compose.yml`
            (e.g. `ports: - "9999:9999"`)
            When running in a container make the host address is `host: 0.0.0.0` in the configuration file.
            You can access the endpoints subsequently via `http://127.0.0.1:9999` or your machine ip.

The TCP server input module returns HTTP return codes:

- 200: Success
- 400: Bad request
- 401: Unauthorized
"""
from dataclasses import dataclass, field
from threading import Thread
from typing import Dict, Any
import socketserver
import socket
import json

# Internal imports.
import config
from modules.base.base import send_data
from modules.inputs.base.base import AbstractInputModule, AbstractVariableModule, AbstractTagModule, models

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = True
"""Is this module public?"""
__description__: str = "This module is creates a tcp server and receives data from the incoming connections."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = []
"""Define your requirements here."""


class InputModule(AbstractInputModule):
    """
    Class for the input module.

    :param configuration: The configuration object of the module.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module creates a TCP server. " \
                       "This is the base connection and required for the according variable and tag modules."
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
        host: str = field(
            metadata=dict(description="The host address of the server.",
                          required=False),
            default="0.0.0.0")
        port: int = field(
            metadata=dict(description="The port of the server.",
                          required=False),
            default=9999)
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
        self.server = None
        """The TCP server."""
        self.registered_modules = {}
        """The variable and tag modules register themselves here with the client_key as key."""

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            self.server = self.ThreadedTCPServer((self.configuration.host, self.configuration.port),
                                                 self.ThreadedTCPRequestHandler)
            # We store the class instance in the server instance since it is running in an own class.
            self.server.server_instance = self
            self.server.registered_modules = self.registered_modules

            # Start a thread with the server - that thread will then start one more thread for each request.
            Thread(target=self.server.serve_forever,
                   daemon=True,
                   name="TCP_Server_Input_Module_{0}".format(self.configuration.id)).start()

            self.logger.info("Successfully created and started server '{0}'."
                             .format(f"{self.configuration.host}:{self.configuration.port}"))
            return True
        except Exception as e:
            self.logger.critical("Something went wrong while creating and starting server '{0}': {1}"
                                 .format(f"{self.configuration.host}:{self.configuration.port}", str(e)),
                                 exc_info=config.EXC_INFO)
            return False

    def stop(self):
        """
        Method for stopping the module. Is called by the main thread.
        """
        # self.server._BaseServer__shutdown_request = True
        self.server.shutdown()
        self.server.server_close()

    class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
        """
        The request handler called in a new thread for each connection.
        """

        def handle(self):
            """
            Process the received data by the client.
            """
            authenticated = False
            module = None
            while self.server.server_instance.active:
                try:
                    data = self.request.recv(1024).strip().decode("utf-8")
                    if not data:
                        # No more data was send by the client.
                        break
                    if not authenticated:
                        try:
                            json_data = json.loads(data)
                            client_key = json_data.get('client_key', None)
                            # Try to get the according variable.
                            module = self.server.registered_modules.get(client_key, None)
                            if not module:
                                raise ConnectionRefusedError("Provided client_key '{0}' is unknown.".format(client_key))
                            if not self.server.server_instance.configuration.anonymous:
                                username = json_data.get('username', None)
                                password = json_data.get('password', None)
                                if not username or not password:
                                    raise ConnectionRefusedError("No username or password were provided.")
                                if username != self.server.server_instance.configuration.username or \
                                        password != self.server.server_instance.configuration.password:
                                    raise ConnectionRefusedError("Provided username '{0}' or password "
                                                                 "are wrong.".format(username))
                            # Everything was good.
                            authenticated = True
                            self.server.server_instance.logger.info(
                                "Client '{0}' with client_key '{1}' successfully connected."
                                .format(self.client_address[0], client_key))
                            self.request.sendall(bytes(str(200), encoding="utf-8"))
                        except ConnectionRefusedError as e:
                            self.server.server_instance.logger.warning("Received unauthenticated request from '{0}': "
                                                                       "{1}".format(self.client_address[0], str(e)))
                            # Send 401 response for unauthorized request to client.
                            self.request.sendall(bytes(str(401), encoding="utf-8"))
                            break
                        except Exception as e:
                            self.server.server_instance.logger.warning("Received request from '{0}',"
                                                                       " which could not be processed: {1}"
                                                                       .format(self.client_address[0], str(e)))
                            # Send 400 response for bad input to client.
                            self.request.sendall(bytes(str(400), encoding="utf-8"))
                            break
                    else:
                        # Check if received data is valid json.
                        try:
                            json_data = json.loads(data)
                            # Send 200 response for success to client.
                            self.request.sendall(bytes(str(200), encoding="utf-8"))
                            # Get the fields and tags from the send data.
                            fields = json_data.get('fields', None)
                            tags = json_data.get('tags', None)
                            # Give th received data to the according module.
                            module.view(fields=fields, tags=tags)
                        except Exception as e:
                            self.server.server_instance.logger.error(
                                "Could not process received data: {0}".format(str(e)),
                                exc_info=config.EXC_INFO)
                            # Send 400 response for bad input to client.
                            self.request.sendall(bytes(str(400), encoding="utf-8"))
                except ConnectionResetError:
                    # Unexpectedly closed by client.
                    self.server.server_instance.logger.info("Client '{0}' with client_key '{1}' disconnected."
                                                            .format(self.client_address[0],
                                                                    getattr(module, 'client_key', 'Unknown')))
                    break

    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        """
        A threaded TCP server.
        """
        pass


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
    description: str = "This module forwards incoming data containing the defined client key."
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
        client_key: str = field(
            metadata=dict(description="A unique key for identifying the client.",
                          required=False),
            default="client1")

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.

        :returns: True if successfully started, otherwise false.
        """
        self.input_module_instance.registered_modules[self.configuration.client_key] = self
        return True

    def view(self, fields, tags):
        """
        This receives data from the tcp server.
        """
        self._data_change(models.Data(measurement=self.configuration.measurement,
                                      fields=fields,
                                      tags=tags))

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
    description: str = "This module forwards the last received data containing the client key if requested."
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
        client_key: str = field(
            metadata=dict(description="A unique key for identifying the client.",
                          required=False),
            default="client1")

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        self.input_module_instance.registered_modules[self.configuration.client_key] = self
        self.fields = {}

    def view(self, fields, tags):
        """
        This receives data from the tcp server.
        """
        self.fields = fields

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        return self.fields
