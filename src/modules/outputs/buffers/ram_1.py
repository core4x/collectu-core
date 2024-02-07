"""
When the application is shut down, the still buffered data can be stored in a json file (created at `/data/buffer`)
if buffer_to_file is True.

**Note:**   The file is not a valid json. To make it a valid json,
            the complete content has to be embedded into `[` and `]`.
"""
import os
from dataclasses import dataclass, field
import queue
import pathlib
from typing import Optional

# Internal imports.
from modules.outputs.base.base import AbstractOutputModule, models
from models.validations import Range


class OutputModule(AbstractOutputModule):
    """
    Class for the output module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module stores data to be buffered in an internal queue."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    can_be_buffer: bool = True
    """If True, the child has to implement 'store_buffer_data' and 'get_buffer_data'."""

    @dataclass
    class Configuration(models.OutputModule):
        """
        The configuration model of the module.
        """
        buffer_size: int = field(
            metadata=dict(description="The number of buffered data elements per module.",
                          required=False,
                          validate=Range(min=1, max=10000)),
            default=100)
        buffer_to_file: bool = field(
            metadata=dict(
                description="Shall the still buffered data be stored in a json file on application closure.",
                required=False),
            default=True)

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
        super().__init__(configuration=configuration)
        self.queue_dict = {}
        """A dictionary containing all created queues with the module_name as key and the queue as value."""

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        if self.configuration.buffered:
            self.logger.warning("'buffered' is true. But data, which could not be processed, can not be buffered.")
        return super().start()

    def stop(self):
        """
        Method for stopping the output module. Is called by the main thread.
        """
        for module_name, module_queue in self.queue_dict.copy().items():
            if not module_queue.empty() and self.configuration.buffer_to_file:
                # This is the file path including the file name.
                file = os.path.join('..', 'data', 'buffer', '{0}.json').format(module_name)
                # Create directory.
                pathlib.Path(os.path.join('..', 'data', 'buffer',
                                          str(pathlib.Path(module_name + '.json').parents[0]))).mkdir(parents=True,
                                                                                                      exist_ok=True)
                # Open the file in 'appending' mode. Start writing to the end of the file.
                file_stream = open(file, 'a')
                while not module_queue.empty():
                    data_dict = module_queue.get()
                    file_stream.write('{0},\n'.format(data_dict))
                    file_stream.flush()
                    module_queue.task_done()
                file_stream.close()

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        # Do nothing.
        pass

    def store_buffer_data(self, module_id: str, data: dict) -> bool:
        """
        Store data to be buffered in queue.

        :param module_id: The id of the output module for which the data is buffered.
        :param data: The data to be buffered.

        :returns: True if successfully buffered, otherwise false.
        """
        success = False
        try:
            if module_id not in self.queue_dict:
                # Create a new queue for this module_name.
                self.queue_dict[module_id] = queue.Queue(maxsize=self.configuration.buffer_size)
            if not self.queue_dict[module_id].full():
                self.queue_dict[module_id].put(data)
                success = True
            else:
                self.logger.error("The internal buffer of queue '{0}' exceeded the buffer size '{1}'. "
                                  "Could not store data in buffer."
                                  .format(module_id, str(self.configuration.buffer_size)))
        except Exception as e:
            self.logger.error("Could not store data to be buffered: {0}".format(str(e)))
        finally:
            return success

    def get_buffer_data(self, module_id: str) -> Optional[dict]:
        """
        Get the oldest element from queue.

        :param module_id: The id of the output module for which the buffered data is requested.

        :returns: The buffered data (only one element is given back per request).
        """
        data = None
        try:
            if module_id in self.queue_dict:
                module_queue = self.queue_dict[module_id]
                data = module_queue.get()
                module_queue.task_done()
        except Exception as e:
            self.logger.error("Could not get buffered data: {0}.".format(str(e)))
        finally:
            return data
