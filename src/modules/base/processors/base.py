"""
This is the base class of all processor modules. All implemented processor modules have to be derived from this class.
The derived child class has to be named 'ProcessorModule'.
"""
from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional
import threading
import inspect
import queue
import time

# Internal imports.
import config
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
        Continuously drains the data queue and processes each item by invoking _run.

        Intended to be started once in a dedicated daemon thread when thread_safe mode is enabled.
        Blocks on the queue with a timeout so the loop can exit cleanly when self.active is set to False.

        Errors raised during processing are caught and logged per item so that a single
        failing item does not halt the queue worker.
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
                if not inspect.iscoroutinefunction(self._run):
                    data = self._run(data)
                else:
                    data = AbstractModule._invoke_async(self._run, data)
                # Call the subsequent links.
                self._call_links(data)
            except Exception as e:
                self.logger.error("Something went wrong while executing processor module {0} ({1}): {2}"
                                  .format(self.configuration.module_name, self.configuration.id, str(e)),
                                  exc_info=config.EXC_INFO)

    def run(self, data: models.Data):
        """
        External entry point for passing data into the module.

        Validates the incoming data against the module's field and tag requirements before processing.
        What happens next depends on thread_safe mode:

          - thread_safe disabled: _run is called directly on the calling thread and
            the result is forwarded to downstream links before returning.
          - thread_safe enabled: data is placed on the internal queue and processed
            by a dedicated queue worker thread. The queue worker is started lazily on
            the first call. Incoming data is silently dropped if the queue has reached
            config.STOP_LIMIT to prevent unbounded memory growth; a warning is logged
            at every config.WARNING_LIMIT interval while the queue is oversized.

        Data objects with no measurement set are ignored and not forwarded.

        :param data: The data object to process.
        :raises utils.data_validation.ValidationError: If field or tag requirements are not satisfied.
                The error is caught internally and logged rather than propagated to the caller.
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
                    messages = utils.data_validation.format_message(tag_validation_messages)
                    raise utils.data_validation.ValidationError(
                        "Invalid tag input data: {0}".format(" ".join(messages)))

                if data.measurement:
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
                        if not inspect.iscoroutinefunction(self._run):
                            data = self._run(data)
                        else:
                            data = AbstractModule._invoke_async(self._run, data)
                        # Call the subsequent links.
                        self._call_links(data)
        except Exception as e:
            self.logger.error("Something went wrong while executing processor module {0} ({1}): {2}"
                              .format(self.configuration.module_name, self.configuration.id, str(e)),
                              exc_info=config.EXC_INFO)

    @abstractmethod
    def _run(self, data: models.Data) -> models.Data:
        """
        Internal method for executing the module. May be implemented as either a regular
        or an async method — both are supported:

            # Synchronous:
            def _run(self, data: models.Data) -> models.Data:
                ...
                return data

            # Asynchronous:
            async def _run(self, data: models.Data) -> models.Data:
                await some_io_operation()
                ...
                return data

        The method receives the current data object, applies whatever transformation or
        enrichment the module is responsible for, and returns the (possibly modified)
        data object. The returned object is then forwarded to all downstream links by
        the calling infrastructure — _run itself should not call _call_links.

        :param data: The data object.
        :returns: The data object after processing.
        """
        # Implement the custom processor module logic here.
        ...
        return data

    @classmethod
    def get_test_data(cls) -> list[dict]:
        """
        Provides test data for validating the module's _run logic in isolation.

        Implementing this method is optional. When test data is provided, the test runner calls _run directly
        for each entry without invoking start, stop, or any surrounding infrastructure.
        Field and tag requirement validation is also skipped during the test phase.

        :returns: A list of dicts, each containing:
                  module_config: The module configuration as a YAML string.
                  input_data:    A data object (measurement, fields, tags) fed into _run.
                  output_data:   The expected data object returned by _run.
                  An empty list signals that no tests are defined for this module.
        """
        test_data = []
        return test_data
