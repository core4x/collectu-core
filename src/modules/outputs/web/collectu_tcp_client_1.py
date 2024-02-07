"""
**Note:**   The client sends the client_key and authentication (if required)
as json string in the first message after connection.

Example:

```json
{"client_key": "client1", "username": "admin", "password": "admin"}
```
"""
import socket
from dataclasses import dataclass, field
from threading import Thread
import json
import time

# Internal imports.
import config
from modules.outputs.base.base import AbstractOutputModule, models


class OutputModule(AbstractOutputModule):
    """
    Class for the console output module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module sends the data to a given tcp server."
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
        client_key: str = field(
            metadata=dict(description="A unique key for identifying the client.",
                          required=False),
            default="client1")
        host: str = field(
            metadata=dict(description="The host address of the endpoint.",
                          required=False),
            default="127.0.0.1")
        port: int = field(
            metadata=dict(description="The port of the endpoint.",
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
        # Calls the base init method.
        super().__init__(configuration=configuration)
        self.client = None
        """The TCP client."""
        self.reconnecting = False
        """True, if we are currently trying to reconnect."""
        self.retrying = False
        """Are we currently trying to reconnect the client."""

    def stop(self):
        """
        Method for stopping the module. Is called by the main thread.
        """
        self.client.shutdown(2)
        self.client.close()

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.configuration.host, self.configuration.port))

            if self.configuration.anonymous:
                self.client.sendall(bytes(json.dumps({"client_key": self.configuration.client_key},
                                                     default=str),
                                          encoding="utf-8"))
            else:
                self.client.sendall(bytes(json.dumps({"client_key": self.configuration.client_key,
                                                      "username": self.configuration.username,
                                                      "password": self.configuration.password}),
                                          encoding="utf-8"))
            response = self.client.recv(1024).strip().decode("utf-8")
            if "200" in response:
                if not self.reconnecting:
                    # If it is the initial connection we set reconnecting to true,
                    # all subsequent calls are retries and we do not have to start the thread again.
                    self.reconnecting = True
                    # Start the queue processing for storing incoming data.
                    Thread(target=self._process_queue,
                           daemon=False,
                           name="Queue_Worker_{0}".format(self.configuration.id)).start()
                self.logger.info("Successfully connected tcp client to '{0}:{1}'.".format(self.configuration.host,
                                                                                          self.configuration.port))
                return True
            elif "400" in response:
                self.logger.critical("Could not connect tcp client '{0}': Request was not in the correct json format."
                                     .format(self.configuration.id))
                return False
            elif "401" in response:
                self.logger.critical("Could not connect tcp client '{0}': Client_key, username or password were wrong."
                                     .format(self.configuration.id))
                return False
            else:
                self.logger.critical("Could not connect tcp client '{0}': Unknown response from server: {1}."
                                     .format(self.configuration.id, str(response)))
                return False

        except Exception as e:
            self.logger.critical("Could not connect tcp client '{0}': {1}".format(self.configuration.id, str(e)),
                                 exc_info=config.EXC_INFO)
            return False

    def _reconnect(self):
        """
        Try to reconnect the client.
        """
        self.retrying = True
        sleeper = 1
        """A variable holding the sleep time for the pause between reconnect tries."""
        while self.active and not self.client:
            self.logger.error("Trying to reconnect...", exc_info=config.EXC_INFO)
            if not self.start():
                self.client = None
                time.sleep(sleeper)
                # Increase the sleep time when the connection was not successful.
                # But limit the maximal sleep time to 10 seconds.
                if sleeper <= 10:
                    sleeper += 1
        else:
            self.retrying = False

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        if not self.client:
            self._buffer(data=data, invalid=False)
            if not self.retrying:
                self._reconnect()
        try:
            self.client.sendall(bytes(json.dumps(data.__dict__, default=str), encoding="utf-8"))
            response = self.client.recv(1024).strip().decode("utf-8")
            if "200" not in response:
                self.logger.error("Could not send data to tcp server with the endpoint '{0}:{1}'. Response: {2}"
                                  .format(self.configuration.host, str(self.configuration.port),
                                          str(response)))
        except (ConnectionResetError, ConnectionRefusedError, OSError) as e:
            self.client = None
            self._buffer(data=data, invalid=False)
        except Exception as e:
            self.logger.error("Something unexpected went wrong while trying to store data: {0}"
                              .format(str(e)), exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
