"""
Set up the logging system.
"""
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import socket
import threading
import uuid
from typing import Optional

# Internal imports.
import config
import data_layer
import models


def threaded(function):
    """
    Decorator to run the called function in a separate thread.
    """

    def run(*args, **kwargs):
        threading.Thread(target=function, daemon=False, args=args, kwargs=kwargs,
                         name="Logging_{0}".format(uuid.uuid4())).start()

    return run


class TracebackInfoFilter(logging.Filter):
    """
    Clear the exception (stacktrace/traceback) on log records.

    CAUTION: The order of the filtering matters. Console logging has to be the last added logger.
    Otherwise, the stacktrace is cleared before the log was written to the file.
    """

    def __init__(self):
        super().__init__()

    def filter(self, record) -> Optional[bool]:
        """
        Sets the stacktrace info to None.

        :param: The log record.
        :returns: Always True.
        """
        if not config.EXC_INFO:
            record._exc_info_hidden = record.exc_info
            record.exc_info = None
            # Clear the exception traceback text cache, if created.
            record.exc_text = None
        elif hasattr(record, "_exc_info_hidden"):
            record.exc_info = record._exc_info_hidden
            del record._exc_info_hidden
        return True


class LoggingTrigger(logging.Handler):
    """
    Custom logging handler, which gets triggered when a new logging message is generated.
    """

    def __init__(self, levels, *args, **kwargs):
        super(LoggingTrigger, self).__init__(*args, **kwargs)
        self.levels = levels
        """The logging levels of the messages, which shall be stored in the output modules."""

    @threaded
    def emit(self, record):
        """
        This method creates an own thread for execution.
        So, the calling threads are not blocked until the storage has finished.

        :param record: The log record.
        """
        # Store messages of given levels.
        if record.levelname in self.levels:
            log_object = models.Data(measurement="Logs",
                                     fields={
                                         "level": str(record.levelname),
                                         "message": str(record.msg),
                                         "name": str(record.name.rsplit('.')[-1]),
                                         "module": ".".join(
                                             (record.name.split("." + record.module, 1)[0],
                                              record.module)).replace(
                                             config.APP_NAME.lower() + ".", "", 1),
                                     },
                                     tags={
                                         "level": str(record.levelname),
                                         "hostname": socket.gethostname(),
                                         "name": str(record.name.rsplit('.')[-1]),
                                         "module": ".".join(
                                             (record.name.split("." + record.module, 1)[0],
                                              record.module)).replace(
                                             config.APP_NAME.lower() + ".", "", 1),
                                     })
            if record.exc_text:
                # Add the stacktrace.
                log_object.fields["stacktrace"] = str(record.exc_text)

            # Store the log message in the according module entry of the data layer if it already exists.
            module_entry = data_layer.module_data.get(str(record.name.rsplit('.')[-1]), None)
            if module_entry is not None:
                module_entry.latest_log = log_object

            # Store the latest logs in the manager list.
            data_layer.latest_logs.append(log_object)


def start(logger: logging.Logger):
    """
    Setting of all logging settings.

    :param logger: The logger of main.py.
    """
    try:
        # The main level for all loggers.
        logger.setLevel(logging.DEBUG)
        # This includes also sub modules. BasicConfig applies to all scripts (also imported modules).
        """
        logging.basicConfig(level=logging.WARNING,
                            format='%(levelname)s - %(processName)s - %(threadName)s - '
                                   '%(name)s:%(lineno)d - %(message)s')
        """

        # ===========================
        # FILE LOGGING
        # ===========================
        # Set the path to the file.
        file = os.path.join(os.path.dirname(__file__), '..', '..', 'logs', 'Logs.log')
        # Create file handler which creates every day a new file (after five files are created, they are overwritten).
        file_logging = TimedRotatingFileHandler(filename=file,
                                                when="d",
                                                interval=1,
                                                backupCount=5)
        file_logging.setLevel(logging.WARNING)
        formatter_file = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(processName)s - %(threadName)s - %(pathname)s:%(lineno)d - %(name)s - %(message)s')
        file_logging.setFormatter(formatter_file)
        logger.addHandler(file_logging)

        # ===========================
        # OUTPUT MODULE LOGGING
        # ===========================
        # Instantiate the output module logging handler.
        output_module_logging = LoggingTrigger(levels=["INFO", "WARNING", "ERROR", "CRITICAL"])
        if config.DEBUG:
            output_module_logging.levels.append("DEBUG")
        logger.addHandler(output_module_logging)

        # ===========================
        # CONSOLE LOGGING
        # ===========================
        console_logging = logging.StreamHandler(sys.stdout)
        console_logging.addFilter(TracebackInfoFilter())
        if config.DEBUG:
            console_logging.setLevel(logging.DEBUG)
        else:
            console_logging.setLevel(logging.INFO)

        format_1 = '%(levelname)s - %(processName)s - %(threadName)s - %(name)s:%(lineno)d: %(message)s'
        """Complete format."""
        format_2 = '%(levelname)s - %(name)s:%(lineno)d: %(message)s'
        """Simplified format (without process and thread info)."""
        format_3 = '%(levelname)s - %(pathname)s:%(lineno)d: %(message)s'
        """Simplified format with the path name instead of the logger name (without process and thread info)."""
        format_4 = '%(levelname)s - %(pathname)s:%(lineno)d - %(name)s - %(message)s'
        """Simplified format with the path name instead of the logger name (without process and thread info)."""
        format_5 = '%(levelname)s - %(processName)s - %(pathname)s:%(lineno)d - %(name)s - %(message)s'
        """Simplified format with the path name instead of the logger name (without process and thread info)."""
        formatter_console = logging.Formatter(format_3)
        console_logging.setFormatter(formatter_console)
        logger.addHandler(console_logging)
        logger.info("Successfully created logger.")
    except Exception as e:
        logger.critical("Failed to set up the logging system: {0}".format(str(e)),
                        exc_info=config.EXC_INFO)
        sys.exit(1)
