"""
This is the base class of all processor modules. All implemented processor modules have to be derived from this class.
The derived child class has to be named 'ProcessorModule'.
"""
from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional
import threading
import queue
import time

# Internal imports.
import config
import data_layer
import models
from modules.base.base import AbstractModule
import utils.data_validation


class AbstractProcessorModule(AbstractModule):
    """
    !!!The derived child class has to be named 'ProcessorModule'!!!

    Abstract base class for the processor module.
    This class shows the required methods to be implemented by the derived child.

    Use: super().__init__(configuration)

    to call this base initialization when implementing the ProcessorModule __init__.

    :param configuration: The configuration object of the module.
    """
    field_requirements: list[str] = []
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the processor module.
        """
        pass

    def __init__(self, configuration: Configuration, thread_safe: bool = False):
        super().__init__(configuration=configuration)
        self.current_input_data: Optional[models.Data] = None
        """The currently received data object. Used for replacing dynamic variables with local data."""
        self.queue: queue.Queue = queue.Queue()
        """A queue containing all the received data to be processed."""
        self._thread_safe: bool = thread_safe
        """If enabled, _run is only called by one thread like for output modules. 
        This has to be set before the execution of the start method."""
        self._first_execution: bool = True
        """If the module was called by its first link, this is set to false."""

    def _process_queue(self):
        """
        Call this method during start-up in a separate thread.
        """
        while self.active:
            try:
                data = self.queue.get(block=True, timeout=1)  # This blocks until timeout.
                self.queue.task_done()
            except queue.Empty:
                time.sleep(0)
                continue
            # Set the last received data for dynamic variables.
            self.current_input_data = data
            # We do not thread, since the output modules may not be thread safe.
            try:
                data = self._run(data=data)
                # Call the subsequent links.
                self._call_links(data)
            except Exception as e:
                self.logger.error("Something went wrong while executing processor module {0} ({1}): {2}"
                                  .format(self.configuration.module_name, self.configuration.id, str(e)),
                                  exc_info=config.EXC_INFO)

    def run(self, data: models.Data):
        """
        External method for executing the module.

        :param data: The data object.
        """
        try:
            if self.active:
                # Set the current data object.
                self.current_input_data = data
                # Validate the field input data.
                valid_field_data, field_requirement_index, field_validation_messages = utils.data_validation.validate(
                    data=data.fields, requirements=self.field_requirements)
                if not valid_field_data:
                    messages = utils.data_validation.format_message(field_validation_messages)
                    raise utils.data_validation.ValidationError(
                        "Invalid field input data: {0}".format(" ".join(messages)))
                # Validate the tag input data.
                valid_tag_data, tag_requirement_index, tag_validation_messages = utils.data_validation.validate(
                    data=data.tags, requirements=self.tag_requirements)
                if not valid_tag_data:
                    messages = utils.data_validation.format_message(field_validation_messages)
                    raise utils.data_validation.ValidationError(
                        "Invalid tag input data: {0}".format(" ".join(messages)))

                if data.fields and data.measurement:
                    if self._thread_safe:
                        if self._first_execution:
                            self._first_execution = False
                            # Start the queue processing for storing incoming data.
                            threading.Thread(target=self._process_queue,
                                             daemon=False,
                                             name="Queue_Worker_{0}".format(self.configuration.id)).start()
                        if self.queue.qsize() > config.WARNING_LIMIT and self.queue.qsize() % config.WARNING_LIMIT == 0:
                            self.logger.warning("You are probably trying to store more data then we can process. "
                                                "We have currently '{0}' elements in our queue to store."
                                                .format(str(self.queue.qsize())))
                        if self.queue.qsize() < config.STOP_LIMIT:
                            # Queue the data to be stored.
                            self.queue.put(data)
                    else:
                        # Execute the actual module.
                        data = self._run(data)
                        # Call the subsequent links.
                        self._call_links(data)
        except Exception as e:
            self.logger.error("Something went wrong while executing processor module {0} ({1}): {2}"
                              .format(self.configuration.module_name, self.configuration.id, str(e)),
                              exc_info=config.EXC_INFO)

    @abstractmethod
    def _run(self, data: models.Data) -> models.Data:
        """
        Internal method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        # Implement the custom processor module logic here.
        ...
        return data

    @classmethod
    def get_test_data(cls) -> list[dict]:
        """
        Provides the test data for processor modules.
        A processor module does not have to provide test data.
        If test data is provided, the _run method is executed without calling other methods like start or stop.
        The validation functionality (field and tag requirements) is skipped during the test phase.

        :returns: A list containing test data with the keys:
                  module_config: The configuration of the module as yaml string.
                  input_data: The input data object with measurement, fields and tags.
                  output_data: The expected output data object with measurement, fields and tags.
        """
        test_data = []
        return test_data
