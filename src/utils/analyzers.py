"""
Some helpful functions for analyzing application behaviour.
"""
import time
import logging
import threading
import functools

# Internal imports.
import config

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


def log_all_threads(interval: int = 0):
    """
    Logs all running threads.
    When logging continuously, function has to be called in a separate thread.

    :param interval: The interval for logging all running threads. If none or 0, the threads are only logged once.

    Example:

    from threading import Thread
    Thread(target=log_all_threads,
           daemon=True,
           args=(2,)).start()
    """
    while True:
        logger.info(
            "Running threads: " + str([f"{thread.name} (daemon: {thread.daemon})" for thread in threading.enumerate()]))
        if interval == 0:
            break
        time.sleep(interval)


def timing(f):
    """
    A wrapper for logging the required execution time of a function.

    Example:

    @timing
    def test():
        ...
    """

    @functools.wraps(f)
    def wrap(*args, **kwargs):
        start = time.perf_counter()
        ret = f(*args, **kwargs)
        logger.info("The function '{:s}' took {:.3f} ms for execution"
                    .format(f.__name__, (time.perf_counter() - start) * 1000.0))
        return ret

    return wrap
