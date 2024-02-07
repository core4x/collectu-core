"""
The Console output module prints the data to the console using logger.debug().

**Note:** Make sure, that the environment variable DEBUG=1. Otherwise, the message will not be visible.
"""
import threading
from dataclasses import dataclass, field
from typing import Dict, Any

# Internal imports.
import config
from modules.outputs.base.base import AbstractOutputModule, models
from models.validations import OneOf


class OutputModule(AbstractOutputModule):
    """
    Class for the console output module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module prints the data to the console using logger.debug()."
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
        level: str = field(
            metadata=dict(
                description="The log level used for logging the data.",
                required=False,
                validate=OneOf(['debug', 'info', 'error', 'warning', 'critical'])),
            default="debug")

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
        super().__init__(configuration=configuration)

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.

        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {
            "level": ['debug', 'info', 'error', 'warning', 'critical']
        }

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        # Start the queue processing for storing incoming data.
        threading.Thread(target=self._process_queue,
                         daemon=False,
                         name="Queue_Worker_{0}".format(self.configuration.id)).start()
        return True

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        try:
            if self.configuration.level == "info":
                self.logger.info(data)
            elif self.configuration.level == "warning":
                self.logger.warning(data)
            elif self.configuration.level == "error":
                self.logger.error(data)
            elif self.configuration.level == "critical":
                self.logger.critical(data)
            else:
                self.logger.debug(data)
        except Exception as e:
            self.logger.error("Something went wrong while trying to store data: {0}."
                              .format(str(e)),
                              exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
