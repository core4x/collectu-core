"""
This class is used (in models/configuration.py) to restart modules, whose initial connection were not successful.
"""
from threading import Thread
import time
import logging
from typing import Optional

# Internal imports.
import config
import data_layer
import models

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


class RetryStart:
    """
    Execute the start method of a module in the retry_interval until the max_attempts is reached.

    :param module: The module, whose start procedure has to be retried.
    :param retry_interval: The sleep time in seconds between retry attempts (> 0).
    :param max_attempts: TThe maximal number of retries. If none is given, it is tried forever.
    """

    def __init__(self,
                 module: models.ModuleData,
                 retry_interval: int = config.RETRY_INTERVAL,
                 max_attempts: Optional[int] = config.MAX_ATTEMPTS):
        if retry_interval <= 0:
            raise Exception("The retry interval has to be bigger than 0.")
        self.module = module
        self.retry_interval = retry_interval
        self.max_attempts = max_attempts
        self.running = True
        """Is the retry procedure running."""
        logger.info("Start retry procedure in the interval of {0} s in order to start '{1}'."
                    .format(str(self.retry_interval), module.module_name))
        Thread(target=self._retry_module_start,
               daemon=True,
               name="Retry_Worker_{0}".format(module.module_name)).start()

    def stop(self):
        """
        Stop the retry procedure.
        """
        self.running = False

    def _retry_module_start(self):
        """
        This internal function is called by the public function in a separate thread.
        This function executes the start method of a module in the retry_interval until the max_attempts is reached.
        """
        attempt_counter = 1
        while self.running and data_layer.running:
            logger.info("Trying to start '{0}' in the {1} attempt..."
                        .format(self.module.module_name, attempt_counter))
            if self.module.instance.start():
                # Start was successful.
                self.running = False

            if self.max_attempts is not None:
                if attempt_counter >= self.max_attempts:
                    logger.info("Reached maximal number of attempts ({0}) of retrying to start module '{1}'."
                                .format(self.max_attempts, self.module.module_name))
                    self.running = False

            # Increase the attempt_counter.
            attempt_counter += 1
            # Sleep until next retry attempt.
            time.sleep(self.retry_interval)
