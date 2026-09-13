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
from queue import Queue, Full, Empty
from typing import Any, Optional
from collections.abc import Callable, Hashable
import copy
import ast
import time

# Internal imports.
import config
import data_layer
import models
import utils.plugin_interface
from metrics import data_context_map, _DataContext, metrics_registry


class DynamicVariableException(Exception):
    """
    Base class for dynamic variable errors.
    The exception contains an error message.
    """
    pass


class QueueMonitor:
    """
    Logs how full a queue is and how long its workers are busy - once per change, not once per data object.

    Everything is reported by the threads putting data into the queue. For the queue of a module, these are
    the link workers of all modules linked to it, so the state is only changed under a lock: each message
    is logged once, however many threads observe the same state at the same time.

    All workers of a link share one monitor. Each of them reports the size of its own queue and the largest
    one counts - otherwise a single blocked worker and its idle siblings would report the link as full and
    as recovered in turns.

    Each limit has a hysteresis, so a fill level oscillating around it does not log again and again:

    - Warning limit: a warning for each multiple of config.WARNING_LIMIT the queue grows into, which was not
      reported yet. Re-armed, with an info message, once the queue fell below half of config.WARNING_LIMIT.
    - Stop limit: an error for the first data object dropped because the queue is full. Re-armed, with an
      info message stating the number of dropped data objects, once the queue fell 1 % below config.STOP_LIMIT.
    - Slow workers: a warning once the first worker is busy with a data object for longer than
      config.SLOW_WORKER_TIMEOUT. Re-armed once every worker reported as slow was seen idle again.
    """

    def __init__(self, logger: logging.Logger, name: str, hint: str = ""):
        """
        :param logger: The logger instance of the module the queue belongs to.
        :param name: Whom the queue is for, e.g. "linked module 'id'". Used in the log messages.
        :param hint: An optional explanation appended to the warning and error messages about the queue.
        """
        self.logger = logger
        self.name = name
        self.hint = f" {hint}" if hint else ""
        self._lock = threading.Lock()
        """Guards the state below."""
        self._sizes: dict[Hashable, int] = {}
        """The latest reported size of each queue sharing this monitor."""
        self._warned_multiple: int = 0
        """The highest multiple of config.WARNING_LIMIT reported since the warnings were re-armed."""
        self._dropped: int = 0
        """The number of data objects dropped since the queue became full. Zero while it is not full."""
        self._slow_workers: set[Hashable] = set()
        """The workers reported as slow, which were not seen idle since."""

    def update(self, size: int, key: Hashable = None):
        """
        Reports the size of a queue after data was put into it.

        :param size: The number of data objects in the queue.
        :param key: Identifies the queue, if several queues share this monitor.
        """
        warning_limit = max(1, config.WARNING_LIMIT)
        messages: list[tuple[int, str]] = []
        with self._lock:
            self._sizes[key] = size
            size = max(self._sizes.values())

            if self._dropped and size + config.STOP_LIMIT // 100 < config.STOP_LIMIT:
                messages.append((logging.INFO, f"Queue for {self.name} is back below the stop limit. "
                                               f"Dropped {self._dropped} data object(s) in the meantime."))
                self._dropped = 0

            multiple = size // warning_limit
            if multiple > self._warned_multiple:
                self._warned_multiple = multiple
                if not self._dropped:  # Growing is no news once the queue was reported to be full.
                    messages.append((logging.WARNING, f"Queue for {self.name} is filling up "
                                                      f"({size}/{config.STOP_LIMIT} data objects).{self.hint}"))
            elif self._warned_multiple and size + warning_limit // 2 < warning_limit:
                self._warned_multiple = 0
                messages.append((logging.INFO, f"Queue for {self.name} is back below the warning limit "
                                               f"({warning_limit} data objects)."))

        # Logged outside the lock, so a slow log handler does not hold up the other threads.
        for level, message in messages:
            self.logger.log(level, message)

    def record_drop(self, key: Hashable = None):
        """
        Reports a data object dropped because a queue is full.

        :param key: Identifies the queue, if several queues share this monitor.
        """
        with self._lock:
            self._sizes[key] = max(self._sizes.get(key, 0), config.STOP_LIMIT)
            self._dropped += 1
            if self._dropped > 1:
                return
        self.logger.error(f"Queue for {self.name} is full ({config.STOP_LIMIT} data objects).{self.hint} "
                          f"Dropping data...")

    def update_worker(self, key: Hashable, busy_for: Optional[float]):
        """
        Reports how long a worker has been busy with its current data object.

        :param key: Identifies the worker.
        :param busy_for: The seconds the worker has been busy, or None if it is idle.
        """
        with self._lock:
            if busy_for is None:
                self._slow_workers.discard(key)
                return
            if busy_for <= config.SLOW_WORKER_TIMEOUT or key in self._slow_workers:
                return
            self._slow_workers.add(key)
            if len(self._slow_workers) > 1:
                return
        self.logger.warning(f"Worker for {self.name} has been processing for {busy_for:.1f}s "
                            f"(threshold: {config.SLOW_WORKER_TIMEOUT}s). "
                            f"Downstream module may be blocked or overloaded.")


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
    :param monitor: Logs the state of the link. Shared by all workers of the same link.
    """

    stop_flush_share: float = 0.8
    """
    The share of the stop timeout a worker may spend on forwarding its remaining backlog.

    The rest of the timeout is the margin for the data object which is already being forwarded
    when the deadline is reached. A worker can only notice the deadline between two data objects,
    so without that margin a worker which does exactly what it is asked would still be reported
    as leaked whenever it holds a backlog.
    """

    def __init__(
            self,
            configuration_id: str,
            module_id: str,
            logger: logging.Logger,
            forward_latest_data_only: bool = False,
            monitor: Optional[QueueMonitor] = None
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
        :param monitor: Logs the state of the link. Pass the same monitor to all workers of a link, so the
            link is logged about once instead of once per worker. Defaults to a monitor of its own.
        """
        self.module_id = module_id
        self.logger = logger
        self.forward_latest_data_only = forward_latest_data_only
        self.monitor: QueueMonitor = monitor if monitor is not None else QueueMonitor(
            logger=logger, name=f"linked module '{module_id}'")
        """Logs how full the queue is and how long the worker is busy."""

        # Slow-worker tracking (shared by both modes, written only by the worker thread).
        self.processing_since: Optional[float] = None

        self.stop_deadline: Optional[float] = None
        """
        The point in time (time.monotonic) after which the worker gives up on its backlog.

        Set by signal_stop, unset while the worker is running. Without it, a queue holding up
        to config.STOP_LIMIT data objects would have to be worked off completely before the
        sentinel at its tail is reached, which turns a stop request into an unbounded wait.
        """

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

        Replaced and dropped data objects are recorded as drops in the metrics of the linked module.
        Submit is called by every thread forwarding data of the current module, so everything worth
        logging is left to the monitor, which logs it once.

        :param data: The data object to forward to the linked module.
        """
        # Slow-worker check (both modes).
        since = self.processing_since  # Single read; no lock needed for a float in CPython.
        self.monitor.update_worker(key=self, busy_for=None if since is None else time.monotonic() - since)

        # Latest-only mode.
        if self.forward_latest_data_only:
            with self.slot_lock:
                replaced = self.slot is not None
                self.slot = data
            self.has_data.set()  # Wake the worker (idempotent if already set).
            if replaced:
                self._record_drop()
            return

        # Queue mode. Checking for a full queue first would race with the other submitting threads.
        try:
            self.queue.put_nowait(data)
        except Full:
            self._record_drop()
            self.monitor.record_drop(key=self)
            return
        self.monitor.update(size=self.queue.qsize(), key=self)

    def _record_drop(self, count: int = 1):
        """
        Records dropped data objects in the metrics of the linked module, since the data was meant for it.

        :param count: The number of dropped data objects.
        """
        metrics = metrics_registry.get(self.module_id)
        if metrics is not None:
            metrics.record_drop(count)

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

        Stops when a ``None`` sentinel value is received, or when the backlog is still not worked
        off by the time the stop deadline set by signal_stop is reached. The remaining data is
        dropped in that case — holding the thread open any longer would only leak it, since the
        sentinel sits behind a backlog which can hold up to config.STOP_LIMIT data objects.
        """
        while True:
            if self.stop_deadline is not None and time.monotonic() >= self.stop_deadline:
                dropped = self._discard_backlog()
                if dropped:
                    self.logger.warning(f"Worker for linked module '{self.module_id}' could not work off its "
                                        f"backlog within the stop timeout. Dropping {dropped} data object(s).")
                    self._record_drop(dropped)
                break
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

    def _discard_backlog(self) -> int:
        """
        Empties the queue.

        :returns: The number of discarded data objects, not counting the stop sentinel.
        """
        discarded = 0
        while True:
            try:
                data = self.queue.get_nowait()
            except Empty:
                return discarded
            self.queue.task_done()
            if data is not None:
                discarded += 1

    def signal_stop(self, timeout: Optional[float] = None):
        """
        Ask the worker thread to stop, without waiting for it.

        In latest-only mode, this wakes the worker so it can detect the stop flag.

        In queue mode, a ``None`` sentinel value is added to the queue to terminate the worker loop.
        The sentinel sits at the tail of the backlog, so a deadline is set as well: the worker
        forwards what it can within stop_flush_share of the timeout and drops the rest.

        Separated from join so a module with several workers can signal them all first and then
        wait for them in parallel, instead of paying the full timeout once per worker.

        :param timeout: The seconds until the worker has to be gone.
            Defaults to config.STOP_TIMEOUT.
        """
        timeout = config.STOP_TIMEOUT if timeout is None else timeout
        self.stop_deadline = time.monotonic() + timeout * self.stop_flush_share
        if self.forward_latest_data_only:
            with self.slot_lock:
                self.stop_flag = True
                discarded = self.slot is not None
                self.slot = None
            self.has_data.set()  # Wake the thread so it can see stop_flag.
            if discarded:
                self._record_drop()
        else:
            try:
                self.queue.put_nowait(None)
            except Full:
                # A full queue means the worker is not waiting for data anyway,
                # so it ends at the deadline instead of at the sentinel.
                pass

    def join(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the worker thread to exit.

        :param timeout: The maximum seconds to wait. Defaults to config.STOP_TIMEOUT.
        :returns: True if the thread has exited, false if it is still running.
        """
        self.thread.join(timeout=max(0.0, config.STOP_TIMEOUT if timeout is None else timeout))
        return not self.thread.is_alive()

    def stop(self, timeout: Optional[float] = None) -> bool:
        """
        Stop the worker thread gracefully and wait for it to exit.

        Never blocks longer than the given timeout. A linked module which blocks forever inside
        run() must not be able to hold up a stop routine - if it does, the thread is left behind
        as a daemon thread and reported by the caller.

        :param timeout: The maximum seconds to wait. Defaults to config.STOP_TIMEOUT.
        :returns: True if the thread has exited, false if it is still running.
        """
        timeout = config.STOP_TIMEOUT if timeout is None else timeout
        deadline = time.monotonic() + timeout
        self.signal_stop(timeout=timeout)
        return self.join(timeout=deadline - time.monotonic())


class QueueWorker:
    """
    Starts the one thread working off the queue of an output module or a thread-safe processor module.

    The thread is started by the first data object and leaves once the module is stopped. If the module is
    restarted in place, the next data object starts a new thread - unless the previous one did not notice the
    stop yet and simply carries on. It only notices between two data objects, and an idle queue keeps it
    waiting for up to a second, so a quick restart usually finds it still running.

    Starting the thread and leaving happen under one lock. Run is called by the workers of all links, so
    without it several of them could start a thread at once, or the thread could leave right after run found
    it still running - leaving the module with two threads calling _run, or with none at all.
    """

    def __init__(self, module: "AbstractModule", target: Callable[[], None]):
        """
        :param module: The module whose queue is worked off.
        :param target: The loop working off the queue. Has to ask keep_running before each data object.
        """
        self._module = module
        self._target = target
        self._lock = threading.Lock()
        """Guards _thread."""
        self._thread: Optional[threading.Thread] = None
        """The thread working off the queue. None before the first data object, and again once the thread left."""

    def start(self):
        """
        Starts the thread, unless it is running. Called for every data object.
        """
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._target,
                                                daemon=False,
                                                name="Queue_Worker_{0}".format(self._module.configuration.id))
                self._thread.start()

    def keep_running(self) -> bool:
        """
        Asked by the thread before each data object. Once it returns False, the thread is no longer registered
        and has to return, since the next data object may start its successor right away.

        :returns: True as long as the module is active.
        """
        with self._lock:
            if self._module.active:
                return True
            self._thread = None
            return False


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
        for package in self.third_party_requirements:
            satisfied, message = utils.plugin_interface.requirement_is_installed(package)
            if not satisfied:
                self.logger.warning(message)
                utils.plugin_interface.install_plugin_requirement(package)
        try:
            # Import the required third party packages.
            self.import_third_party_requirements()
        except ImportError as e:
            self.logger.critical("Could not import required packages: {0}. Please try to install '{1}'."
                                 .format(str(e), ', '.join(map(str, self.third_party_requirements))))
            raise
        self.active: bool = self.configuration.active
        """Is the module currently active.
        Not the same as self.configuration.active, which represents the general state!"""
        self.started: threading.Event = threading.Event()
        """Is the module ready to process data.
        Set automatically as soon as the start method returns. Modules whose start method blocks
        for the lifetime of the module have to set this themselves before entering their loop."""
        self._readiness_timed_out: bool = False
        """Did waiting for the readiness already time out once.
        Prevents stalling every single data object for a module which never reports readiness."""
        self._workers_lock = threading.Lock()
        """A lock for checking existing workers thread-safe."""
        self._workers: dict[str, list[ModuleWorker]] = {}
        """Worker threads for calling linked modules, per linked module. An empty list in persistent-worker mode
        means the workers do not exist yet or were stopped - _call_links creates them when there is data to forward."""
        self._worker_index: dict[str, int] = {}
        """Round-robin worker index for each linked module."""

        for module_id in getattr(self.configuration, "links", []):
            # Registers the link. Its workers, if any, are created by _call_links with the first data object.
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

    def _await_started(self) -> bool:
        """
        Waits until the module reported that it is ready to process data.

        The module logic must not be executed before the start method established whatever it
        needs (e.g. a database connection), since the start method is called in its own thread
        and is retried until it succeeds - data can arrive long before that.

        Called for every data object, since a module can also lose its readiness again (e.g. a
        start method which blocks and raises on a connection loss).

        Waits at most config.START_TIMEOUT seconds. A module which neither returns from its start
        method nor sets self.started itself is not blocked forever, it only loses the guarantee -
        and it is only waited for once, so such a module does not stall every data object by the
        full timeout. As soon as the module reports its readiness, the guarantee applies again.

        :returns: True if the module is ready, False if it was stopped or the timeout was reached.
        """
        if self.started.is_set():
            # Readiness was (re-)reported, so wait again should it be lost later on.
            self._readiness_timed_out = False
            return True
        if self._readiness_timed_out:
            # Already waited the full timeout for this module without success.
            return False
        waited: int = 0
        while self.active and not self.started.wait(timeout=1):
            waited += 1
            if waited >= config.START_TIMEOUT:
                self.logger.warning("The module did not report to be ready within {0} s. "
                                    "Processing the data anyway.".format(config.START_TIMEOUT))
                self._readiness_timed_out = True
                return False
        return self.started.is_set()

    def _await_input_module(self) -> bool:
        """
        Waits until the input module this module depends on reported that it is ready.

        Tag and variable modules normally use a resource of their input module (e.g. a single
        database connection shared by all of its tag and variable modules). That resource only
        exists once the start method of the input module established it, and the input module
        is started in its own thread, so it can still be connecting when this module starts.

        Waits at most config.START_TIMEOUT seconds, and returns early if either module is
        deactivated in the meantime. Modules without an input module return immediately.

        :returns: True if there is no input module or it is ready, False otherwise.
        """
        input_module_instance = getattr(self, "input_module_instance", None)
        if input_module_instance is None:
            return True
        started = getattr(input_module_instance, "started", None)
        if started is None:
            # An input module which does not provide the readiness flag can not be awaited.
            return True
        if started.is_set():
            return True
        waited: int = 0
        while self.active and input_module_instance.active and not started.wait(timeout=1):
            waited += 1
            if waited >= config.START_TIMEOUT:
                self.logger.warning("The input module '{0}' did not report to be ready within {1} s. "
                                    "Starting anyway."
                                    .format(input_module_instance.configuration.id, config.START_TIMEOUT))
                return False
        return started.is_set()

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
            # Deliberately without a timeout. This also carries _run of the input, output and
            # processor base classes, which may legitimately run for a long time, and returning
            # early would hand the caller a result the coroutine has not produced yet. An async
            # stop which never returns is caught one level up, by the bounded wait in
            # Configuration.stop, and reported there.
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

    def _create_workers(self, module_id: str, worker_count: int) -> list[ModuleWorker]:
        """
        Creates and starts the persistent workers for the link to a module.

        The workers share one monitor, so the link is logged about once, not once per worker.

        :param module_id: The id of the linked module.
        :param worker_count: The number of workers to create.
        :returns: The started workers.
        """
        monitor = QueueMonitor(logger=self.logger, name=f"linked module '{module_id}'")
        return [
            ModuleWorker(
                configuration_id=self.configuration.id,
                module_id=module_id,
                logger=self.logger,
                forward_latest_data_only=getattr(self.configuration, "forward_latest_data_only", False),
                monitor=monitor
            )
            for _ in range(worker_count)
        ]

    def _stop_workers(self, timeout: Optional[float] = None) -> list[str]:
        """
        Shuts down all persistent link worker threads.

        All workers are signaled before the first one is waited for, so the timeout is spent
        once for the whole module instead of once per worker.

        The wait is bounded. A worker whose linked module blocks forever inside run() can not be
        killed - Python has no way of terminating a thread - so it is left behind as a daemon
        thread and named in the returned list, instead of holding up the entire stop routine.

        A stopped worker can not be started again, so the workers are taken out while the links stay
        registered. Should the module be restarted in place, _call_links creates new workers for them.

        :param timeout: The maximum seconds to wait for all workers together.
            Defaults to config.STOP_TIMEOUT.
        :returns: The names of the worker threads which are still running.
        """
        timeout = config.STOP_TIMEOUT if timeout is None else timeout
        with self._workers_lock:
            workers = [worker for worker_list in self._workers.values() for worker in worker_list]
            for module_id in self._workers:
                self._workers[module_id] = []
        if not workers:
            return []

        deadline = time.monotonic() + timeout
        for worker in workers:
            worker.signal_stop(timeout=timeout)
        for worker in workers:
            worker.join(timeout=deadline - time.monotonic())

        leaked = [worker.thread.name for worker in workers if worker.thread.is_alive()]
        if leaked:
            self.logger.error("The following worker thread(s) of module '{0}' did not stop within {1} s and are "
                              "leaked: {2}. The linked module is most probably blocking inside its run method."
                              .format(self.configuration.id, timeout, ", ".join(leaked)))
        return leaked

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
        if not self.active or not data_layer.running:
            return
        if not data.measurement.strip():
            return

        # A thread which outlives the stop routine of its module - a module which ignores
        # self.active, or one stuck in a call that does not return - can not be killed, since
        # Python has no way of terminating a thread. What it must not do is keep feeding data
        # into a configuration it no longer belongs to.
        module_entry = data_layer.module_data.get(self.configuration.id)
        if module_entry is None:
            # The module was removed, or the whole configuration was stopped.
            self.logger.error(f"Could not find module '{self.configuration.id}' in data layer.")
            return
        if module_entry.instance is not self:
            # The module id is registered again, but with a newer instance than this one.
            return
        module_entry.latest_data = data

        # Retrieve existing context (set by a previous _call_links hop) or establish this as the flow origin.
        now = time.monotonic()
        existing_ctx = data_context_map.get(data)
        pipeline_ts = existing_ctx.pipeline_ts if existing_ctx else now
        source_id = existing_ctx.source_id if existing_ctx else self.configuration.id
        visited = existing_ctx.visited if existing_ctx else frozenset()

        current_links = set(getattr(self.configuration, "links", []))
        worker_count = getattr(self.configuration, "worker_count_per_link", 1)

        remaining = current_links - visited
        if not remaining and existing_ctx is not None:
            # No unvisited link remains - true sink, or every link loops back into an already-visited module.
            # Either way, this is the end of this branch of the flow.
            # Without a context, the data did not arrive via a link, so there is no flow to measure - a module
            # without links would otherwise report a zero latency flow from itself to itself.
            metrics_registry.record_end_to_end(
                source_id=source_id,
                output_id=self.configuration.id,
                seconds=now - pipeline_ts,
            )

        with self._workers_lock:
            existing = set(self._workers.keys())

            # Add newly linked modules.
            for module_id in current_links - existing:
                if worker_count == 0:
                    self.logger.info(f"Detected new link to module '{module_id}'. Using spawn mode.")
                else:
                    self.logger.info(f"Detected new link to module '{module_id}'. Starting worker.")
                self._workers[module_id] = []

            # Remove workers for unlinked modules.
            removed = {}
            for module_id in existing - current_links:
                self.logger.info(f"Detected removed link to module '{module_id}'. Stopping worker.")
                removed[module_id] = self._workers.pop(module_id)
                self._worker_index.pop(module_id, None)

            # Create the missing workers: for the first data object of a link, and for the first one after a
            # restart in place, since _stop_workers took the stopped workers out. Checked under the lock the
            # stop routine takes them out with - a module stopped since the check above must not get new
            # workers, as nothing would ever stop them.
            if worker_count > 0 and self.active:
                for module_id in self._workers:
                    if not self._workers[module_id]:
                        self._workers[module_id] = self._create_workers(module_id=module_id,
                                                                        worker_count=worker_count)
                        self._worker_index[module_id] = 0

            workers_snapshot = list(self._workers.items())

        # Stop removed workers outside the lock — .stop() blocks until the thread joins.
        # This runs in the data path, so the workers are signaled first and then waited for
        # against a single deadline. A worker which does not make it is left behind rather than
        # blocking the module which is currently forwarding data.
        removed_workers = [worker for worker_list in removed.values() for worker in worker_list]
        if removed_workers:
            deadline = time.monotonic() + config.STOP_TIMEOUT
            for worker in removed_workers:
                worker.signal_stop(timeout=config.STOP_TIMEOUT)
            for worker in removed_workers:
                worker.join(timeout=deadline - time.monotonic())
            leaked = [worker.thread.name for worker in removed_workers if worker.thread.is_alive()]
            if leaked:
                self.logger.error("The worker thread(s) of the removed link(s) did not stop within {0} s and are "
                                  "leaked: {1}.".format(config.STOP_TIMEOUT, ", ".join(leaked)))

        for module_id, worker_list in workers_snapshot:
            data_copy = copy.deepcopy(data)

            # Store context for the copy with a fresh link_ts for this specific link.
            # pipeline_ts and source_id are inherited from the flow origin;
            # visited now includes this module, so the next hop's _call_links can detect if it's closing a loop.
            data_context_map.set(data_copy, _DataContext(
                pipeline_ts=pipeline_ts,
                source_id=source_id,
                link_ts=time.monotonic(),  # stamped after copy, per link.
                visited=visited | {self.configuration.id},
            ))

            if worker_count == 0:
                # Spawn mode: each call gets its own thread.
                try:
                    linked = data_layer.module_data[module_id]
                    if linked.instance.active:
                        threading.Thread(
                            target=linked.instance.run,
                            args=(data_copy,),
                            name=f"Link_{self.configuration.id}_to_{module_id}",
                            daemon=True).start()
                except KeyError as e:
                    self.logger.error("Could not find linked module '{0}' in the module data.".format(module_id))
                except Exception as e:
                    self.logger.error("Could not execute linked module '{0}': {1}".format(module_id, str(e)),
                                      exc_info=config.EXC_INFO)
            else:
                # Persistent-worker mode: round-robin dispatch.
                if not worker_list:
                    # The module was stopped meanwhile, and with it its workers.
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
