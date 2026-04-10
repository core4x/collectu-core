"""
This is the base class of all output modules. All implemented output modules have to be derived from this class.
The derived child class has to be named 'OutputModule'.
"""
import time
import inspect
from abc import abstractmethod
from dataclasses import dataclass
import queue
import threading
from typing import Optional

# Internal imports.
import config
import data_layer
import models
import utils.data_validation
from modules.base.base import AbstractModule


class AbstractOutputModule(AbstractModule):
    """
    !!!The derived child class has to be named 'OutputModule'!!!

    Abstract base class for the output module.
    This class shows the required methods to be implemented by the derived child.

    Use: super().__init__(configuration)

    to call this base initialization when implementing the OutputModule __init__.

    :param configuration: The configuration object of the module.
    """
    field_requirements: list[str] = []
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""
    can_be_buffer: bool = False
    """If True, the child has to implement 'store_buffer_data' and 'get_buffer_data'."""

    @dataclass
    class Configuration(models.OutputModule):
        """
        The configuration model of the output module.
        """
        pass

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.queue: queue.Queue = queue.Queue()
        """A queue containing all the received data to be stored."""
        self.current_input_data: Optional[models.Data] = None
        """The currently received data object. Used for replacing dynamic variables with local data."""
        self._first_execution: bool = True
        """If the module was called by its first link, this is set to false."""

    def run(self, data: models.Data):
        """
        External entry point for passing data into the module.

        Validates the incoming data against the module's field and tag requirements,
        updates the latest data entry in the data layer, and enqueues the data for
        processing by the queue worker thread. The queue worker is started lazily on the first call.

        If the queue has reached config.STOP_LIMIT, the data is forwarded to the configured buffer module instead
        of being dropped. If no buffer is configured, the data is lost and an error is logged.

        A warning is logged at every config.WARNING_LIMIT interval while the queue is oversized.
        Data objects with no measurement set are not enqueued or forwarded.

        :param data: The data object to process.
        :raises utils.data_validation.ValidationError: If field or tag requirements
                are not satisfied. The error is caught internally and logged rather than propagated to the caller.
        """
        try:
            if self.active:
                if self._first_execution:
                    self._first_execution = False
                    # Start the queue processing for storing incoming data.
                    threading.Thread(target=self._process_queue,
                                     daemon=False,
                                     name="Queue_Worker_{0}".format(self.configuration.id)).start()
                if self.queue.qsize() > config.WARNING_LIMIT and self.queue.qsize() % config.WARNING_LIMIT == 0:
                    self.logger.error("You are probably trying to store more data then we can process. "
                                      "We have currently '{0}' elements in our queue to store."
                                      .format(str(self.queue.qsize())))

                # Store the data in the latest data entry if a measurement is given.
                if data.measurement:
                    # During the stopping procedure, it could happen that the entry no longer exists.
                    if self.configuration.id not in data_layer.module_data:
                        self.logger.error("Could not find module with id '{0}' in data layer."
                                          .format(str(self.configuration.id)))
                    else:
                        data_layer.module_data[self.configuration.id].latest_data = data

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

                    if self.queue.qsize() < config.STOP_LIMIT:
                        # Queue the data to be stored.
                        self.queue.put(data)
                    else:
                        # Attempt to forward the data to a buffer module.
                        # If no buffer is configured, the data is lost.
                        buffered = self._buffer(data=data, invalid=False)
                        if not buffered:
                            self.logger.error("Could not store data because the queue size exceeded the stop limit "
                                              "and no buffer is configured.")
        except Exception as e:
            self.logger.error("Could not store data in queue: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)

    def _process_queue(self):
        """
        Continuously drains the data queue and processes each item by invoking _run.

        Intended to be started once in a dedicated daemon thread on the first call to run().
        Before consuming from the queue, any data previously offloaded to the buffer module
        is retrieved and processed first to preserve ordering.
        Blocks on the queue with a timeout so the loop can exit cleanly when self.active is set to False.

        Errors raised during processing are caught and logged per item so that a single
        failing item does not halt the queue worker.
        """
        while self.active:
            # Prioritize buffered data before consuming from the live queue.
            data = self._get_buffer()
            if data is None:
                try:
                    data = self.queue.get(block=True, timeout=1)  # This blocks until timeout.
                    self.queue.task_done()
                except queue.Empty:
                    time.sleep(0)
                    continue
            else:
                time.sleep(0)
            # Set the last received data for dynamic variables.
            self.current_input_data = data
            try:
                if not inspect.iscoroutinefunction(self._run):
                    data = self._run(data)
                else:
                    data = AbstractModule._invoke_async(self._run, data)
            except Exception as e:
                self.logger.error("Something went wrong while executing output module {0} ({1}): {2}"
                                  .format(self.configuration.module_name, self.configuration.id, str(e)),
                                  exc_info=config.EXC_INFO)

    @abstractmethod
    def _run(self, data: models.Data):
        """
        Internal method for executing the module logic. Must be implemented by every derived OutputModule class.

        May be declared as either a regular or an async method — both are supported:

            # Synchronous:
            def _run(self, data: models.Data):
                write_to_destination(data)

            # Asynchronous:
            async def _run(self, data: models.Data):
                await async_write_to_destination(data)

        When a connection error prevents the data from being stored, call self._buffer
        with invalid=False so the data is retried once the destination is reachable again.
        If the failure is caused by the data itself (e.g. invalid format), call self._buffer with invalid=True —
        the data is then written to the _bin table and not retried.

        :param data: The data object to be processed.
        """
        try:
            # Implement the custom output module logic here.
            ...
        except Exception as e:
            self.logger.error("Something went wrong while trying to process data: {0}"
                              .format(str(e)), exc_info=config.EXC_INFO)
            # Buffer the data if the failure was caused by a connection error.
            # Use invalid=True if the data itself is malformed, so it is not retried.
            self._buffer(data=data, invalid=False)

    def _buffer(self, data: models.Data, invalid: bool = False) -> bool:
        """
        Forwards data that could not be stored to a configured buffer module.

        If invalid is False, the data is stored under the module's buffer key and will
        be retried by _process_queue once the destination becomes reachable again.
        If invalid is True, the data is stored under the module's bin key and will not
        be retried, since the failure is assumed to be caused by the data itself rather
        than a connectivity problem.

        :param data: The data object to be buffered.
        :param invalid: If True, the data is written to the _bin table and not retried.
        :returns: True if the data was successfully forwarded to the buffer, False otherwise.
        """
        success = False
        try:
            if data_layer.buffer_instance:
                if invalid:
                    success = data_layer.buffer_instance.store_buffer_data(self.configuration.id + "_bin", data)
                else:
                    success = data_layer.buffer_instance.store_buffer_data(self.configuration.id + "_buffer", data)
        except Exception as e:
            self.logger.error("Could not store data in buffer: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)
        return success

    def _get_buffer(self) -> Optional[models.Data]:
        """
        Retrieves the oldest buffered data entry for this module from the buffer module.

        Called by _process_queue before consuming from the live queue so that previously
        buffered data is replayed in order before new data is processed.

        :returns: The oldest buffered data object, or None if no buffer is configured or
                  the buffer is empty.
        """
        data = None
        try:
            if data_layer.buffer_instance:
                data = data_layer.buffer_instance.get_buffer_data(self.configuration.id + "_buffer")
        except Exception as e:
            self.logger.error("Could not get data from buffer: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)
        return data

    def store_buffer_data(self, module_id: str, data: models.Data) -> bool:
        """
        Stores data on behalf of another output module that has nominated this module as its buffer.

        Must be implemented by output modules that set can_be_buffer = True.
        The implementation must be thread-safe, as this method may be called concurrently
        from multiple output module queue workers.

        :param module_id: The id of the output module for which the data is being buffered.
                          Used as the storage key to keep data from different modules separate.
        :param data: The data object to buffer.
        :returns: True if the data was successfully stored, False otherwise.
        """
        success = False
        try:
            ...
        except Exception as e:
            self.logger.error("Could not store data in buffer: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)
        return success

    def get_buffer_data(self, module_id: str) -> Optional[models.Data]:
        """
        Retrieves and removes the oldest buffered data entry for the given module id.

        Must be implemented by output modules that set can_be_buffer = True.
        The implementation must be thread-safe, as this method may be called concurrently
        from multiple output module queue workers.

        :param module_id: The id of the output module whose buffered data is requested.
        :returns: The oldest buffered data object for the given module id, or None if the buffer is empty.
        """
        data = None
        try:
            ...
        except Exception as e:
            self.logger.error("Could not get buffered data: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)
        return data
