"""
This is the base class of all output modules. All implemented output modules have to be derived from this class.
The derived child class has to be named 'OutputModule'.
"""
import time
import uuid
from abc import abstractmethod
from dataclasses import dataclass
import os
import queue
import threading
from typing import Optional

# Internal imports.
import config
import data_layer
import models
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

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread or the retry class.

        :returns: True if successfully started, otherwise false.
        """
        try:
            # Start the queue processing for storing incoming data.
            threading.Thread(target=self._process_queue,
                             daemon=False,
                             name="Queue_Worker_{0}".format(self.configuration.id)).start()
            return True
        except Exception as e:
            self.logger.critical("Something went wrong while trying to start module: {0}".format(str(e)),
                                 exc_info=config.EXC_INFO)
            return False

    def stop(self):
        """
        Method for stopping the output module. Is called by the main thread.
        """
        self.active = False

    def run(self, data: models.Data):
        """
        Method for storing data in a queue.
        Should always be called in a separate thread since some things are done here.

        :param data: The data object.
        """
        try:
            if self.active:
                if self.queue.qsize() > config.WARNING_LIMIT and self.queue.qsize() % config.WARNING_LIMIT == 0:
                    self.logger.error("You are probably trying to store more data then we can process. "
                                      "We have currently '{0}' elements in our queue to store."
                                      .format(str(self.queue.qsize())))

                # Store the data in the latest data entry if fields and a measurement are given.
                if data.fields and data.measurement:
                    # During the stopping procedure, it could happen, that the entry does no longer exist.
                    # We catch it here.
                    if self.configuration.id not in data_layer.module_data:
                        self.logger.error("Could not find module with id '{0}' in data layer."
                                          .format(str(self.configuration.id)))
                    else:
                        data_layer.module_data[self.configuration.id].latest_data = data

                # We store data only, if we are not in test mode, fields and a measurement are given.
                if not bool(int(os.environ.get('TEST', '0'))) and data.fields and data.measurement:
                    if self.queue.qsize() < config.STOP_LIMIT:
                        # Queue the data to be stored.
                        self.queue.put(data)
                    else:
                        # Trying to store the data in the buffer. But if there is no buffer, the data is lost.
                        buffered = self._buffer(data=data, invalid=False)
                        if not buffered:
                            self.logger.error("Could not store data because the queue size exceeded the stop limit "
                                              "and no buffer is configured.")
        except Exception as e:
            self.logger.error("Could not store data in queue: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)

    def _process_queue(self):
        """
        Call this method during start-up in a separate thread.
        """
        while self.active:
            # First we try to get buffer data.
            data = self._get_buffer()
            if data is None:
                try:
                    data = self.queue.get(block=True, timeout=1)  # This blocks until timeout.
                    self.queue.task_done()
                except queue.Empty:
                    # When we receive no data, we try to get buffer data again.
                    time.sleep(0)
                    continue
            # Set the last received data for dynamic variables.
            self.current_input_data = data
            # We do not thread, since the output modules may not be thread safe.
            try:
                self._run(data=data)
            except Exception as e:
                self.logger.error("Something unexpected went wrong while trying to process data: {0}"
                                  .format(str(e)), exc_info=config.EXC_INFO)

    @abstractmethod
    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        try:
            # Implement the custom output module logic here.
            ...
        except Exception as e:
            self.logger.error("Something went wrong while trying to process data. {0}"
                              .format(str(e)), exc_info=config.EXC_INFO)
            # CAUTION: The data object should only be buffered,
            # if a connection error was the original problem for the exception.
            # If the exception was caused by the data itself (e.g. invalid data format etc.),
            # set the invalid flag. The data is then stored in the buffer (_bin table) and not retried.
            self._buffer(data=data, invalid=False)

    def _buffer(self, data: models.Data, invalid: bool = False) -> bool:
        """
        This method receives data, which could not be stored in the output module, because it wasn't accessible.
        The data is sent to a buffer module and stored until the output module is accessible again.

        :param data: The data object, which shall be buffered.
        :param invalid: The data is probably corrupted.
        This is mostly the case, when the storing process failed but the connection is correct.
        The data will be stored in a '_bin' database of the buffer module.
        So, it is not retried to store the data in the actual output module, since it probably causes an exception.

        :returns: True if successfully stored, false if not.
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
        finally:
            return success

    def _get_buffer(self) -> Optional[models.Data]:
        """
        Get buffered data from a buffer module.

        :returns: Returns one entry of the buffered data if there is one. Otherwise, it returns None.
        """
        data = None
        try:
            if data_layer.buffer_instance:
                data = data_layer.buffer_instance.get_buffer_data(self.configuration.id + "_buffer")
        except Exception as e:
            self.logger.error("Could not get data from buffer: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)
        finally:
            return data

    def store_buffer_data(self, module_id: str, data: models.Data) -> bool:
        """
        Store data to be buffered.

        !This method has to be implemented by buffer output modules!
        Make sure this is thread-safe!!!

        :param module_id: The id of the output module for which the data is buffered.
        This shall be used as the identification for the buffered elements.
        :param data: The data to be buffered.

        :returns: True if successfully buffered, otherwise false.
        """
        success = False
        try:
            ...
        except Exception as e:
            self.logger.error("Could not store data in buffer: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)
        finally:
            return success

    def get_buffer_data(self, module_id: str) -> Optional[models.Data]:
        """
        Get the oldest element.

        !This method has to be implemented by buffer output modules!
        Make sure this is thread-safe!!!

        :param module_id: The id of the output module for which the buffered data is requested.

        :returns: The buffered data (only one element is given back per request).
        """
        data = None
        try:
            ...
        except Exception as e:
            self.logger.error("Could not get buffered data: {0}".format(str(e)),
                              exc_info=config.EXC_INFO)
        finally:
            return data
