"""
This is the base class for all modules.
"""
__version__: int = 1
"""The auto-generated version of the module."""
from abc import ABC
import logging
import os
import asyncio
import inspect
import threading
from queue import Queue
from typing import Any, Optional
import copy
import ast
import time

# Internal imports.
import config
import data_layer
import models
import utils.plugin_interface


class DynamicVariableException(Exception):
    """
    Base class for dynamic variable errors.
    The exception contains an error message.
    """
    pass


class ModuleWorker:
    """
    A single persistent worker thread for one linked module.

    :param configuration_id: The id of the current module.
    :param module_id: The id of the linked module.
    :param logger: The logger instance of the parent module.
    :param forward_latest_data_only: If True, only the most recent submitted data object is kept.
    Any pending data is overwritten by newer arrivals.
    Use for high-frequency sensors where backlog processing is meaningless.
    If False (default), all data objects are queued and processed in order.
    """

    def __init__(
            self,
            configuration_id: str,
            module_id: str,
            logger: logging.Logger,
            forward_latest_data_only: bool = False
    ):
        """
        Initialize the worker thread for the linked module.

        Depending on ``forward_latest_data_only``, the worker either runs in:

        - **Latest-only mode**: keeps only the newest submitted data object.
        - **Queue mode**: processes all submitted data objects in FIFO order.

        :param configuration_id: The id of the current module.
        :param module_id: The id of the linked module.
        :param logger: The logger instance of the parent module.
        :param forward_latest_data_only: Whether only the latest data object should be processed.
        """
        self.module_id = module_id
        self.logger = logger
        self.forward_latest_data_only = forward_latest_data_only

        # Slow-worker tracking (shared by both modes, written only by the worker thread).
        self.processing_since: Optional[float] = None
        self.slow_worker_warned: bool = False

        if forward_latest_data_only:
            # Latest-only mode.
            self.slot_lock: threading.Lock = threading.Lock()
            self.slot: Optional[models.Data] = None
            self.has_data: threading.Event = threading.Event()
            self.stop_flag: bool = False
            target = self._loop_latest
        else:
            # Queue mode.
            self.queue: Queue = Queue(maxsize=config.STOP_LIMIT)
            self.last_warned_multiple: int = 0
            """Number showing multiple for the last warning log message. Shows that the queue is growing."""
            self.error_issued: bool = False
            """Flag showing if a error log message, that the queue is full, was issued."""
            target = self._loop

        self.thread = threading.Thread(
            target=target,
            name="Link_{0}_to_{1}".format(configuration_id, module_id),
            daemon=True)
        self.thread.start()

    def submit(self, data: models.Data):
        """
        Submit a data object for processing by the worker.

        In latest-only mode, any previously pending data is replaced by the newly submitted object.

        In queue mode, the data is appended to the internal queue unless the queue is full,
        in which case the data is dropped.

        :param data: The data object to forward to the linked module.
        """
        # Slow-worker check (both modes).
        since = self.processing_since  # Single read; no lock needed for a float in CPython.
        if since is not None:
            elapsed = time.monotonic() - since
            if elapsed > config.SLOW_WORKER_TIMEOUT and not self.slow_worker_warned:
                self.logger.warning(
                    f"Worker for linked module '{self.module_id}' has been processing "
                    f"for {elapsed:.1f}s (threshold: {config.SLOW_WORKER_TIMEOUT}s). "
                    f"Downstream module may be blocked or overloaded.")
                self.slow_worker_warned = True
        elif self.slow_worker_warned:
            # Worker finished; reset for the next occurrence.
            self.slow_worker_warned = False

        # Latest-only mode.
        if self.forward_latest_data_only:
            with self.slot_lock:
                self.slot = data
            self.has_data.set()  # Wake the worker (idempotent if already set).
            return

        # Queue mode.
        qsize = self.queue.qsize()
        if self.queue.full():
            if not self.error_issued:
                self.logger.error(f"Queue for linked module '{self.module_id}' is full "
                                  f"({config.STOP_LIMIT} data objects). Dropping data...")
                self.error_issued = True
            return
        elif qsize < config.STOP_LIMIT - 100 and self.error_issued:  # 100 as hysteresis band.
            self.logger.info(f"Queue for linked module '{self.module_id}' is back below stop limit.")
            self.error_issued = False

        current_multiple = qsize // config.WARNING_LIMIT
        if current_multiple > self.last_warned_multiple:
            self.logger.warning(f"Queue for linked module '{self.module_id}' is filling up "
                                f"({qsize}/{config.STOP_LIMIT} data objects).")
            self.last_warned_multiple = current_multiple
        elif current_multiple < self.last_warned_multiple:
            if qsize < config.WARNING_LIMIT:
                self.logger.info(f"Queue for linked module '{self.module_id}' is back below warning limit.")
            self.last_warned_multiple = current_multiple

        self.queue.put_nowait(data)

    def _loop_latest(self):
        """
        Worker loop for latest-only mode.

        Waits until new data is available, retrieves the most recent submitted object, clears the slot,
        and executes the linked module.

        If multiple submissions happen while the worker is busy, only the most recent object is processed.
        """
        while True:
            self.has_data.wait()  # Sleep until something arrives.
            with self.slot_lock:
                if self.stop_flag:
                    break
                data = self.slot  # Grab current latest.
                self.slot = None
                self.has_data.clear()  # Reset: new submits re-set it.

            if data is None:
                continue  # Spurious wake (shouldn't happen).

            try:
                linked = data_layer.module_data.get(self.module_id)
                if linked and linked.instance.active:
                    self.processing_since = time.monotonic()  # Mark start.
                    linked.instance.run(data)
            except Exception as e:
                self.logger.error(f"Could not execute linked module '{self.module_id}': {e}",
                                  exc_info=config.EXC_INFO)
            finally:
                self.processing_since = None  # Always clear, even on exception.

    def _loop(self):
        """
        Worker loop for queue mode.

        Continuously consumes data objects from the queue and forwards them to the linked module in submission order.

        Stops when a ``None`` sentinel value is received.
        """
        while True:
            data = self.queue.get()
            if data is None:
                break
            try:
                linked = data_layer.module_data.get(self.module_id)
                if linked and linked.instance.active:
                    self.processing_since = time.monotonic()  # Mark start.
                    linked.instance.run(data)
            except Exception as e:
                self.logger.error(f"Could not execute linked module '{self.module_id}': {e}",
                                  exc_info=config.EXC_INFO)
            finally:
                self.processing_since = None  # Always clear, even on exception.
                self.queue.task_done()

    def stop(self):
        """
        Stop the worker thread gracefully.

        In latest-only mode, this wakes the worker so it can detect the stop flag.

        In queue mode, a ``None`` sentinel value is added to the queue to terminate the worker loop.

        This method blocks until the worker thread has fully exited.
        """
        if self.forward_latest_data_only:
            with self.slot_lock:
                self.stop_flag = True
                self.slot = None
            self.has_data.set()  # Wake the thread so it can see stop_flag.
        else:
            self.queue.put(None)
        self.thread.join()


_thread_local = threading.local()
"""
Thread-local storage for persistent async event loops.

Each thread that calls _invoke_async gets its own event loop created on first use
and reused for all subsequent calls on that thread. The loop is stored under
_thread_local.event_loop and is never shared between threads.
"""


class AbstractModule(ABC):
    """
    All modules have to be derived from this one.

    :param configuration: The configuration object of the module.
    """
    version: int = __version__
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = ""
    """A short description."""
    author: str = ""
    """The author name."""
    email: str = ""
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""

    def __init__(self, configuration):
        self.logger: logging.Logger = logging.getLogger(
            f"{config.APP_NAME.lower()}.{configuration.module_name}.{configuration.id}")
        """The logger of the instantiated child class."""
        self.configuration = configuration
        """The configuration of the module."""
        try:
            self.import_third_party_requirements()
            """Import the required third party packages."""
        except ImportError as e:
            if bool(int(os.environ.get('AUTO_INSTALL', '0'))):
                self.logger.warning("Third party requirements are not fulfilled: {0}. "
                                    "Trying to auto install required third party packages: '{1}'."
                                    .format(str(e), ', '.join(map(str, self.third_party_requirements))))
                for package in self.third_party_requirements:
                    utils.plugin_interface.install_plugin_requirement(package)
                self.import_third_party_requirements()
            else:
                self.logger.critical("Could not import required packages: {0}. Please try to install '{1}'."
                                     .format(str(e), ', '.join(map(str, self.third_party_requirements))))
                raise ImportError
        self.active: bool = self.configuration.active
        """Is the module currently active.
        Not the same as self.configuration.active, which represents the general state!"""
        self._workers_lock = threading.Lock()
        """A lock for checking existing workers thread-safe."""
        self._workers: dict[str, list[ModuleWorker]] = {}
        """Worker threads for calling linked modules."""
        self._worker_index: dict[str, int] = {}
        """Round-robin worker index for each linked module."""

        worker_count = getattr(self.configuration, "worker_count_per_link", 1)
        for module_id in getattr(self.configuration, "links", []):
            if worker_count > 0:
                # Persistent-worker mode.
                self._workers[module_id] = [
                    ModuleWorker(
                        configuration_id=self.configuration.id,
                        module_id=module_id,
                        logger=self.logger,
                        forward_latest_data_only=getattr(
                            self.configuration, "forward_latest_data_only", False)
                    )
                    for _ in range(worker_count)
                ]
                self._worker_index[module_id] = 0
            else:
                # Spawn mode: register the link with an empty list as a sentinel.
                self._workers[module_id] = []

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        Import here the third party requirements as follows:
          global package
          import package

        :returns: True if the import was successful.
        """
        pass

    @staticmethod
    def get_config_data(input_module_instance=None) -> dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {}

    def start(self):
        """
        Method for starting the module. Is called by a separate thread.
        InputModules and OutputModules normally connect to a data source.
        VariableModules start a subscription. May be implemented as either a regular or an async method.
        The start method is only called if the module is active (self.configuration.active).
        """
        ...

    @staticmethod
    def _invoke_async(method, *args, **kwargs):
        """
        Executes an async method from a synchronous context.

        Used internally by __init_subclass__ to safely call async stop()
        implementations. Follows the same two-branch strategy used across all
        module base classes:

          - No running loop: a persistent thread-local event loop is reused.
          - Running loop detected: the coroutine is dispatched to a dedicated
            daemon thread to avoid a deadlock.

        :param method: The async method to invoke.
        :param args: Positional arguments forwarded to the method.
        :param kwargs: Keyword arguments forwarded to the method.
        """
        try:
            asyncio.get_running_loop()
            result, exc = [None], [None]

            def _run_in_thread():
                try:
                    result[0] = asyncio.run(method(*args, **kwargs))
                except Exception as e:
                    exc[0] = e

            t = threading.Thread(target=_run_in_thread, daemon=True)
            t.start()
            t.join()
            if exc[0]:
                raise exc[0]
            return result[0]

        except RuntimeError:
            loop = getattr(_thread_local, "event_loop", None)
            if loop is None or loop.is_closed():
                loop = asyncio.new_event_loop()
                _thread_local.event_loop = loop
            return loop.run_until_complete(method(*args, **kwargs))

    def __init_subclass__(cls, **kwargs):
        """
        Automatically wraps any stop() defined in a subclass so worker cleanup always
        runs, without touching child implementations.

        Supports both synchronous and asynchronous stop() implementations.
        If the child defines async def stop(), the wrapper invokes it via _invoke_async so
        the coroutine is actually awaited rather than silently discarded.
        """
        super().__init_subclass__(**kwargs)
        if "stop" in cls.__dict__:
            original_stop = cls.__dict__["stop"]

            def _wrapped_stop(self, *args, **kwargs):
                try:
                    if inspect.iscoroutinefunction(original_stop):
                        AbstractModule._invoke_async(original_stop, self, *args, **kwargs)
                    else:
                        original_stop(self, *args, **kwargs)
                finally:
                    AbstractModule._stop_workers(self)

            cls.stop = _wrapped_stop

    def _stop_workers(self):
        """
        Shuts down all persistent link worker threads.
        """
        for worker_list in self._workers.values():
            for worker in worker_list:
                worker.stop()

    def stop(self):
        """
        Method for stopping the module. Is called by a separate thread.
        TagModules and ProcessorModules do (normally) not need to implement a stop routine.
        May be implemented as either a regular or an async method — both are supported.
        Worker cleanup always runs after stop() completes, regardless of implementation type.
        """
        self._stop_workers()

    def _call_links(self, data: models.Data):
        """
        Calls all links of the module.
        The linked module is only called if self.active is true.

        When worker_count_per_link > 0, submits data to the persistent round-robin worker pool.

        When worker_count_per_link == 0 (spawn mode), a fresh daemon thread is created for every call instead.
        forward_latest_data_only is ignored in spawn mode.

        :param data: The data object.
        """
        if not data.measurement.strip():
            return

        config_id = self.configuration.id
        module_entry = data_layer.module_data.get(config_id)
        if module_entry is None:
            self.logger.error(f"Could not find module '{config_id}' in data layer.")
        else:
            module_entry.latest_data = data

        current_links = set(getattr(self.configuration, "links", []))
        worker_count = getattr(self.configuration, "worker_count_per_link", 1)

        with self._workers_lock:
            existing = set(self._workers.keys())

            # Add workers for newly linked modules.
            for module_id in current_links - existing:
                if worker_count == 0:
                    self.logger.info(f"Detected new link to module '{module_id}'. Using spawn mode.")
                    self._workers[module_id] = []
                else:
                    self.logger.info(f"Detected new link to module '{module_id}'. Starting worker.")
                    self._workers[module_id] = [
                        ModuleWorker(
                            configuration_id=self.configuration.id,
                            module_id=module_id,
                            logger=self.logger,
                            forward_latest_data_only=getattr(self.configuration, "forward_latest_data_only", False)
                        )
                        for _ in range(worker_count)
                    ]
                    self._worker_index[module_id] = 0

            # Remove workers for unlinked modules.
            removed = {}
            for module_id in existing - current_links:
                self.logger.info(f"Detected removed link to module '{module_id}'. Stopping worker.")
                removed[module_id] = self._workers.pop(module_id)
                self._worker_index.pop(module_id, None)

            workers_snapshot = list(self._workers.items())

        # Stop removed workers outside the lock — .stop() blocks until thread joins.
        for worker_list in removed.values():
            for worker in worker_list:
                worker.stop()

        for module_id, worker_list in workers_snapshot:
            data_copy = copy.deepcopy(data)

            if worker_count == 0:
                # Spawn mode: each call gets its own thread.
                try:
                    linked = data_layer.module_data[module_id]
                    if linked.instance.active:
                        threading.Thread(
                            target=linked.instance.run,
                            args=(data_copy,),
                            name=f"Link_{config_id}_to_{module_id}",
                            daemon=True).start()
                except KeyError as e:
                    self.logger.error("Could not find linked module '{0}' in the module data.".format(module_id))
                except Exception as e:
                    self.logger.error("Could not execute linked module '{0}': {1}".format(module_id, str(e)),
                                      exc_info=config.EXC_INFO)
            else:
                # Persistent-worker mode: round-robin dispatch.
                if not worker_list:
                    self.logger.error(f"Could not find worker(s) for linked module '{module_id}'.")
                    continue
                index = self._worker_index.get(module_id, 0)
                worker_list[index % len(worker_list)].submit(data_copy)
                self._worker_index[module_id] = (index + 1) % len(worker_list)

    def _dyn(self, input_data: Any, data_type: list[str] | str | None = None) -> Any:
        """
        This method receives an input value and replaces all dynamic variables e.g. '${module_id.key}'
        with the current value of the linked module.
        All attributes of a variable possibly containing variables have to be given to this function before applied.

        !CAUTION: we can not guarantee that the data type fits the one defined for the field!
        However, you can try to convert to one of the given data types.
        If a conversion is not possible, we will raise a DynamicVariableException.
        But if more than one dynamic variable was in the input_string, we also return a string.

        If the replacement of the dynamic variable went wrong (e.g. because of a missing value or wrong data type),
        an DynamicVariableException is raised.

        :param input_data: The input data possibly containing dynamic variables.
        :param data_type: The data type we try the dynamic variable. Can be list, dict, str, int, float, or bool.
        :returns: The input with the dynamic variables replaced by the actual value.
        """
        try:
            available_data_types = {"str": str, "bool": bool, "float": float, "int": int, "list": list, "dict": dict}
            """A dictionary containing all available data types for conversion."""

            # To be safe, we make the input_string a string.
            input_string = str(input_data)

            # Convert to list.
            if data_type is None:
                data_type = []
            if not isinstance(data_type, list):
                data_type = [data_type]
            # Make every entry a lowered string.
            converted_data_types: list[type] = []
            for item in data_type:
                key = str(item).lower()

                if key not in available_data_types:
                    raise DynamicVariableException(
                        f"Unknown data type {item}. "
                        f"Allowed types are: {', '.join(available_data_types)}."
                    )

                converted_data_types.append(available_data_types[key])

            extracted_variables: list[str] = []
            """The extracted dynamic variables as str, without the markers (e.g. 'REST_Test.[0]')."""

            def _extract_variables(input_string_temp: str):
                """
                Recursively search for variables in string.
                """
                start = input_string_temp.find("${")
                if start != -1:
                    end = input_string_temp[start:].find("}")
                    if end != -1:
                        end = start + end
                else:
                    # No end found.
                    return

                # Check if the markers were found in the string.
                if start != -1 and end != -1 and start < end:
                    result = input_string_temp[start + len("${"):end]
                elif start != -1 and end == -1:
                    raise DynamicVariableException("Found an incomplete marker in '{0}'.".format(input_string))
                else:
                    # If there are no more markers, we leave this function.
                    return

                extracted_variables.append(result)
                new_input_string = input_string_temp.replace("${" + result + "}", '')
                # Recursively call this function until there are no more dynamic variables.
                _extract_variables(new_input_string)

            # Make input to string to be safe and extract dynamic variables if there are.
            _extract_variables(str(input_string))

            processed_input_string = input_string
            if extracted_variables:
                for variable_text in extracted_variables:
                    module_id = variable_text.split('.', 1)[0]
                    key = variable_text.split('.', 1)[1]
                    if module_id == "local":
                        if getattr(self, "current_input_data", None) is not None:
                            data = self.current_input_data
                            # Check if the key is 'measurement'.
                            if key.lower() == "measurement":
                                value = data.measurement
                            elif key.lower() == "time":
                                value = data.time
                            else:
                                # Check if the key is in the fields dict.
                                value = data.fields.get(key, None)
                                if value is None:
                                    # If it was not in the fields dict, we check if the key is in the tags dict.
                                    value = data.tags.get(key, None)
                                if value is None:
                                    raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                                   "Could not find key '{1}' in fields or tags."
                                                                   .format(input_string, key))
                        else:
                            raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                           "Referenced module has no latest data. "
                                                           "Only tag, output, and processor modules support 'local'."
                                                           .format(input_string))
                    elif module_id == "env":
                        value = os.getenv(key, None)
                        if value is None:
                            raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                           "Could not find key '{1}' in environment variables."
                                                           .format(input_string, key))
                    else:
                        module_entry = data_layer.module_data.get(module_id, None)
                        if module_entry is not None:
                            if module_entry.latest_data is not None:
                                data = module_entry.latest_data
                                # Check if the key is in the fields dict.
                                value = data.fields.get(key, None)
                                if value is None:
                                    # If it was not in the fields dict, we check if the key is in the tags dict.
                                    value = data.tags.get(key, None)
                                if value is None:
                                    raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                                   "Could not find key '{1}' in fields or tags."
                                                                   .format(input_string, key))
                            else:
                                raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                               "Referenced module has no latest data."
                                                               .format(input_string))
                        else:
                            raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                           "Could not find module with the id '{1}'."
                                                           .format(input_string, module_id))

                    # Replace the input with the value.
                    if len(extracted_variables) == 1 and input_string.startswith(
                            "${") and input_string.endswith("}"):
                        # If it was only one dynamic variable, we keep the data type of the input.
                        processed_input_string = value
                    else:
                        # We have to convert it to a string.
                        processed_input_string = processed_input_string.replace(
                            "${" + variable_text + "}", str(value))

            try:
                # This make strings to lists and dicts, if they are.
                processed_input_string = ast.literal_eval(processed_input_string)
            except Exception as e:
                pass

            # Try to convert to the given data type.
            successfully_converted: bool = False
            for defined_data_type in converted_data_types:
                try:
                    if defined_data_type == list:
                        if not isinstance(processed_input_string, list):
                            processed_input_string = [processed_input_string]
                    else:
                        processed_input_string = defined_data_type(processed_input_string)
                    successfully_converted = True
                    break
                except Exception as e:
                    continue
            if not successfully_converted and converted_data_types:
                raise DynamicVariableException(
                    f"Could not convert dynamic variable '{processed_input_string}' "
                    f"to one of the given data types: {', '.join(str(x) for x in data_type)}.")
            return processed_input_string
        except DynamicVariableException:
            raise
        except Exception as e:
            raise DynamicVariableException("Something unexpected went wrong while trying to "
                                           "replace dynamic variable '{0}': {1}"
                                           .format(input_string, str(e)))
