"""
Fixtures shared by the tests.

The app keeps its state in module globals - data_layer, the metrics registry, os.environ - and reads and writes its
files relative to the directory it was started from, which is src. A test that changes any of it has to put it back,
or every test after it runs against what it left behind. GlobalStateTestCase does that for the globals, and
AppTestCase additionally runs each test in a directory of its own, laid out like a checkout.

The fake modules below follow the contract of real modules: an input module holds a connection its variable and tag
modules use, a variable module produces data, a tag module enriches it, a processor transforms it and an output module
is where it ends. Their data is produced by the test, through `emit`, rather than on a schedule of their own.
"""
import collections
import logging.handlers
import os
import queue
import tempfile
import threading
import time
import types
import unittest
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest import mock

# Internal imports.
import config
import configuration as configuration_module
import data_layer
import models
from configuration import Configuration
from metrics import metrics_registry
from modules.base.inputs.base import AbstractInputModule, AbstractTagModule, AbstractVariableModule
from modules.base.outputs.base import AbstractOutputModule
from modules.base.processors.base import AbstractProcessorModule

TIMEOUT: float = 5.0
"""Seconds a test waits for something another thread does. Generous, since CI runners can be slow."""

FAST_TIME = types.SimpleNamespace(time=time.time,
                                  monotonic=time.monotonic,
                                  sleep=lambda seconds: time.sleep(min(seconds, 0.01)))
"""
Stands in for the time module of configuration.py, so its fixed waits do not add up over hundreds of starts and
stops: the half second the stop routine waits for running pipelines, and the retry interval of a failed start.
"""


def wait_for(predicate, timeout: float = TIMEOUT) -> bool:
    """
    Wait until the predicate holds.

    :param predicate: A callable without arguments.
    :param timeout: The maximum seconds to wait.
    :returns: True if the predicate held within the timeout, false otherwise.
    """
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)
    return True


def records_reaching_the_app(test: unittest.TestCase, name: str) -> list[logging.LogRecord]:
    """
    The records of a logger, and of the loggers below it, that reach the handlers of the app - those of the root
    logger, which utils.logging.start sets up - until the end of the test.

    :param test: The test, which removes the handler again when it ends.
    :param name: The name of the logger.
    :returns: The records, filled as they arrive.
    """
    handler = logging.handlers.BufferingHandler(capacity=1000)
    handler.addFilter(logging.Filter(name))
    root = logging.getLogger()
    root.addHandler(handler)
    test.addCleanup(root.removeHandler, handler)
    return handler.buffer


class Inbox:
    """
    Collects what a module receives, and lets a test wait for it.
    """

    def __init__(self):
        self._condition = threading.Condition()
        self.items: list = []
        """Everything received, in order."""

    def append(self, item):
        with self._condition:
            self.items.append(item)
            self._condition.notify_all()

    def wait_for(self, count: int, timeout: float = TIMEOUT) -> bool:
        """
        :param count: The number of items to wait for.
        :param timeout: The maximum seconds to wait.
        :returns: True if at least count items arrived within the timeout.
        """
        with self._condition:
            return self._condition.wait_for(lambda: len(self.items) >= count, timeout=timeout)


class Client(AbstractInputModule):
    """
    An input module holding the connection its variable and tag modules use.
    """
    description = "A client of the tests."

    @dataclass
    class Configuration(models.InputModule):
        """
        The configuration model of the module.
        """
        host: str = field(
            metadata=dict(description="The host to connect to.",
                          required=False),
            default="localhost")

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.connection: Optional[dict[str, Any]] = None
        """The connection, while the module is started."""
        self.start_calls: int = 0
        """How often the start method was called."""

    def start(self):
        self.start_calls += 1
        self.connection = {"host": self.configuration.host}

    def stop(self):
        self.connection = None


class ClientVariable(AbstractVariableModule):
    """
    A variable module of the client. Its data is produced by the test, through emit.
    """
    description = "A variable of the tests."

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        input_module: str = field(
            metadata=dict(description="The id of the input module (inputs.test.client_1).",
                          required=True),
            default=None)

    def emit(self, **fields_) -> models.Data:
        """
        Forward a data object, tagged with the host of the connection of the client.

        :param fields_: The fields of the data object.
        :returns: The data object.
        """
        data = models.Data(measurement=self.configuration.measurement, fields=fields_,
                           tags={"host": self.input_module_instance.connection["host"]})
        self._call_links(data)
        return data


class ClientTag(AbstractTagModule):
    """
    A tag module of the client. Adds the host of the connection of the client.
    """
    description = "A tag of the tests."

    @dataclass
    class Configuration(models.TagModule):
        """
        The configuration model of the module.
        """
        input_module: str = field(
            metadata=dict(description="The id of the input module (inputs.test.client_1).",
                          required=True),
            default=None)
        key: str = field(
            metadata=dict(description="The key the host is stored under.",
                          required=False,
                          dynamic=True),
            default="host")

    def _run(self) -> dict[str, Any]:
        return {self._dyn(self.configuration.key, "str"): self.input_module_instance.connection["host"]}


class Source(AbstractVariableModule):
    """
    A variable module without an input module. Its data is produced by the test, through emit.
    """
    description = "A source of the tests."

    def emit(self, **fields_) -> models.Data:
        """
        Forward a data object.

        :param fields_: The fields of the data object.
        :returns: The data object.
        """
        data = models.Data(measurement=self.configuration.measurement, fields=fields_)
        self._call_links(data)
        return data


class Multiplier(AbstractProcessorModule):
    """
    Multiplies the field 'value'.
    """
    description = "A processor of the tests."
    field_requirements = ["(key value with number)"]

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        factor: int = field(
            metadata=dict(description="The factor.",
                          required=False,
                          dynamic=True),
            default=2)

    def _run(self, data: models.Data) -> models.Data:
        data.fields["value"] = data.fields["value"] * self._dyn(self.configuration.factor, "int")
        return data


class Collector(AbstractOutputModule):
    """
    An output module collecting what it receives.
    """
    description = "An output of the tests."

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.inbox = Inbox()
        """What the module stored."""

    def _run(self, data: models.Data):
        self.inbox.append(data)


class Buffer(AbstractOutputModule):
    """
    An output module which can be the buffer of the others. It keeps what it is handed in memory, per module.
    """
    description = "A buffer of the tests."
    can_be_buffer = True

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self._lock = threading.Lock()
        self.stored: dict[str, list[models.Data]] = collections.defaultdict(list)
        """The buffered data objects, with the key they were stored under."""

    def _run(self, data: models.Data):
        pass

    def store_buffer_data(self, module_id: str, data: models.Data) -> bool:
        with self._lock:
            self.stored[module_id].append(data)
        return True

    def get_buffer_data(self, module_id: str) -> Optional[models.Data]:
        with self._lock:
            entries = self.stored.get(module_id)
            return entries.pop(0) if entries else None


MODULES: dict[str, type] = {
    "inputs.test.client_1": Client,
    "inputs.test.client_1.variable": ClientVariable,
    "inputs.test.client_1.tag": ClientTag,
    "inputs.test.source_1.variable": Source,
    "processors.test.multiplier_1": Multiplier,
    "outputs.test.collector_1": Collector,
    "outputs.test.buffer_1": Buffer,
}
"""The fake modules, by the module name a configuration uses."""


def module_config(module_id: str, module_name: str, **parameters) -> dict[str, Any]:
    """
    The configuration of one module, as the editor writes it - always with the panel it is placed on.

    :param module_id: The id of the module.
    :param module_name: The name of a registered module, usually one of MODULES.
    :param parameters: The other parameters. The version is the one of the fake modules and the panel is the
                       first one unless given.
    :returns: The module configuration.
    """
    return {"id": module_id, "module_name": module_name, "version": 1, "panel": "panel-1", **parameters}


def instance(module_id: str):
    """
    :param module_id: The id of a running module.
    :returns: Its instance.
    """
    return data_layer.module_data[module_id].instance


def close_store(store):
    """
    Close the file of a store of utils.config_store. The app keeps it open for as long as it runs, while a test has
    to close it before its directory can be removed.

    :param store: The store.
    """
    database = getattr(store, "_db", None)
    if database is not None:
        database.close()


class GlobalStateTestCase(unittest.TestCase):
    """
    Puts the global state of the app back after each test.

    What data_layer holds is replaced by empty values for the duration of the test, and the metrics registry and the
    environment variables are restored.
    """

    _DATA_LAYER: tuple[str, ...] = ("version", "running", "settings", "registered_modules", "configuration",
                                    "module_data", "buffer_instance", "dashboard_modules", "mothership_data",
                                    "mothership_tasks", "latest_logs", "last_mothership_sending_error_log",
                                    "last_mothership_receiving_error_log")
    """The attributes of data_layer a test may change."""

    def setUp(self):
        super().setUp()
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)

        saved = {name: getattr(data_layer, name) for name in self._DATA_LAYER}
        self.addCleanup(self._restore_data_layer, saved)
        data_layer.version = "unknown"
        data_layer.running = True
        data_layer.settings = {}
        data_layer.registered_modules = {}
        data_layer.configuration = None
        data_layer.module_data = {}
        data_layer.buffer_instance = None
        data_layer.dashboard_modules = []
        data_layer.mothership_data = {}
        data_layer.mothership_tasks = {}
        data_layer.latest_logs = collections.deque(maxlen=config.NUMBER_OF_BUFFERED_LOGS)
        data_layer.last_mothership_sending_error_log = {}
        data_layer.last_mothership_receiving_error_log = {}

        metrics_registry.reset()
        self.addCleanup(metrics_registry.reset)

    @staticmethod
    def _restore_data_layer(saved: dict[str, Any]):
        for name, value in saved.items():
            setattr(data_layer, name, value)

    def patch_config(self, **values):
        """
        Change constants of config.py until the test ends.

        :param values: The constants and their values.
        """
        patcher = mock.patch.multiple(config, **values)
        patcher.start()
        self.addCleanup(patcher.stop)

    def enter_app_directory(self) -> str:
        """
        Create a directory laid out like a checkout and make its src folder the working directory until the test
        ends - which is where the app runs from, so '../configuration', '../data' and '../settings.ini' are this
        directory's rather than the checkout's.

        :returns: The root of the directory.
        """
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        # Resolved, since the code under test compares resolved paths (/tmp is a link on macOS).
        root = os.path.realpath(directory.name)
        for folder in ("src", "configuration", "data", "logs"):
            os.makedirs(os.path.join(root, folder))
        previous = os.getcwd()
        os.chdir(os.path.join(root, "src"))
        self.addCleanup(os.chdir, previous)
        return root


class _QueueWorkedOff(BaseException):
    """
    Ends the database worker loop of a configuration once its queue is empty. Not an Exception, which the loop
    would catch and log.
    """


class AppTestCase(GlobalStateTestCase):
    """
    Runs each test in a directory of its own, with the fake modules registered and nothing downloaded from the hub.
    """

    def setUp(self):
        super().setUp()
        self.root = self.enter_app_directory()
        os.environ["AUTO_START"] = "0"
        os.environ["AUTO_DOWNLOAD"] = "0"
        os.environ.pop("CONFIG", None)
        data_layer.registered_modules.update(MODULES)
        patcher = mock.patch.object(configuration_module, "time", FAST_TIME)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create_configuration(self) -> Configuration:
        """
        Create the configuration as main.py does, and stop it when the test ends - which also ends the threads of
        its modules, some of which are no daemon threads.

        Its database worker thread is not started. It would outlive the test, since it runs for as long as the app
        does, and work_off_database_queue does its job on the test's thread instead.

        :returns: The configuration.
        """
        with mock.patch.object(Configuration, "_database_worker"):
            configuration = Configuration()
        self.addCleanup(close_store, configuration.config_db)
        self.addCleanup(configuration.stop)
        return configuration

    @staticmethod
    def work_off_database_queue(configuration: Configuration):
        """
        Process the tasks queued for the configuration database on this thread, as the database worker thread does,
        and return once the queue is empty.

        :param configuration: The configuration whose queue is worked off.
        """
        database_queue = configuration.database_queue

        def get(block=True, timeout=None):
            try:
                return queue.Queue.get(database_queue, block=False)
            except queue.Empty:
                raise _QueueWorkedOff()

        with mock.patch.object(database_queue, "get", side_effect=get):
            try:
                Configuration._database_worker(configuration)
            except _QueueWorkedOff:
                pass

    def write_configuration_file(self, filename: str, content: str) -> str:
        """
        Write a file into the configuration directory.

        :param filename: The filename, possibly with subdirectories.
        :param content: The content.
        :returns: The path of the file.
        """
        path = os.path.join(self.root, "configuration", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        return path
