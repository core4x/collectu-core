""""""
from dataclasses import dataclass, field
from threading import Thread
import datetime
import time
from typing import Dict, Any, Union
import math

# Internal imports.
import config
from modules.base.base import send_data
from modules.inputs.base.base import AbstractVariableModule, AbstractTagModule, models
from models.validations import Range

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = True
"""Is this module public?"""
__description__: str = "This module creates sine values in a defined interval."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = []
"""Define your requirements here."""


class VariableModule(AbstractVariableModule):
    """
    A variable module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = __description__
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        amplitude: float = field(
            metadata=dict(description="The amplitude of the wave.",
                          required=False,
                          validate=Range(min=0, max=1000, exclusive=False)),
            default=1)
        sample_points: int = field(
            metadata=dict(description="The number of sample points on the sine function.",
                          required=False,
                          validate=Range(min=0, max=1000, exclusive=True)),
            default=10)
        interval: float = field(
            metadata=dict(description="Interval in seconds in which the module provides the values. "
                                      "If interval is 0, the module is executed once.",
                          required=False,
                          validate=Range(min=0, max=1000, exclusive=False)),
            default=1)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        self.sample_points = []
        for value in range(self.configuration.sample_points):
            self.sample_points.append(((2 * math.pi) / self.configuration.sample_points) * value)
        self.current_index: int = 0

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.
        VariableModules normally start a subscription.

        :returns: True if successfully connected, otherwise false.
        """
        Thread(target=self._generate_data,
               daemon=True,
               name="Variable_Module_{0}".format(self.configuration.id)).start()
        return True

    def _generate_data(self):
        """
        Generates random data in a defined interval.
        """
        # The start time of the execution. Needed for the try to implement a non-shifting execution routine.
        start_time = datetime.datetime.now()
        while self.active:
            try:
                data = models.Data(
                    fields={"sine": self.configuration.amplitude * math.sin(self.sample_points[self.current_index])},
                    measurement=self.configuration.measurement)
                self._data_change(data)
                if self.current_index >= len(self.sample_points) - 1:
                    self.current_index = 0
                else:
                    self.current_index += 1
            except Exception as e:
                self.logger.error("Could not generate data: {0}".format(str(e)), exc_info=config.EXC_INFO)
            # This should prevent shifting a little.
            required_time = datetime.datetime.now() - start_time
            if self.configuration.interval == 0:
                break
            if self.configuration.interval > float(required_time.seconds):
                time.sleep(self.configuration.interval - float(required_time.seconds))
            start_time = datetime.datetime.now()

    @send_data
    def _data_change(self, data: models.Data):
        """
        Is just called by the _data_change function.
        """
        return data


class TagModule(AbstractTagModule):
    """
    A tag module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = __description__
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.TagModule):
        """
        The configuration model of the tag module.
        """
        amplitude: float = field(
            metadata=dict(description="The amplitude of the wave.",
                          required=False,
                          validate=Range(min=0, max=1000, exclusive=False)),
            default=1)
        sample_points: int = field(
            metadata=dict(description="The number of sample points on the sine function.",
                          required=False,
                          validate=Range(min=0, max=1000, exclusive=True)),
            default=1)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        self.sample_points = []
        for value in range(self.configuration.sample_points):
            self.sample_points.append(((2 * math.pi) / self.configuration.sample_points) * value)
        self.current_index: int = 0

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        return {"sine": self.configuration.amplitude * math.sin(self.sample_points[self.current_index])}
