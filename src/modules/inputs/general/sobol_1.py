"""
Sobol’ sequences are low-discrepancy, quasi-random numbers.
Compared to the random generator, the values are more evenly distributed.

The generated sequence is returned as field with the key sequence_index.
Where `index` is depending on the configured dimension.
"""
from dataclasses import dataclass, field
import datetime
import time
from threading import Thread
from typing import Dict, Any, List
import random
import string

# Internal imports.
import config
from models.validations import OneOf, Range
from modules.base.base import send_data
from modules.inputs.base.base import AbstractVariableModule, AbstractTagModule, models

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = True
"""Is this module public?"""
__description__: str = "This module generates a Sobol’ sequence."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = ["scipy==1.8.0"]
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
    description: str = "This module generates a Sobol’ sequence in a defined interval."
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
        interval: float = field(
            metadata=dict(description="Interval in seconds in which the module generates test data. "
                                      "If the interval is 0, it is only executed once.",
                          required=False,
                          validate=Range(min=0, max=1000, exclusive=False)),
            default=1)
        dimensions: int = field(
            metadata=dict(description="The dimension. Defines the number of sequences included in the fields.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=0, max=21201, exclusive=False)),
            default=1)
        lower_bound: List[float] = field(
            metadata=dict(description="The lower bound (inclusive) for each dimension.",
                          required=False,
                          dynamic=False),
            default_factory=list)
        upper_bound: List[float] = field(
            metadata=dict(description="The upper bound (exclusive) for each dimension.",
                          required=False,
                          dynamic=False),
            default_factory=list)
        number: int = field(
            metadata=dict(description="The number of entries in the sequence calculated with: 2^number. "
                                      "Since the number of samples in the sequence has to be power of 2. "
                                      "E.g. number = 3 means 2^3 = 8.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=0, max=1000, exclusive=False)),
            default=3)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.
        :returns: True if the import was successful.
        """
        try:
            global stats
            from scipy import stats
            global np
            import numpy as np
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

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
                sequence = stats.qmc.Sobol(self.configuration.dimensions, scramble=True).random_base2(
                    m=self.configuration.number)
                if self.configuration.lower_bound and self.configuration.upper_bound:
                    sequence = stats.qmc.scale(sequence, self.configuration.lower_bound, self.configuration.upper_bound)
                fields = {}
                for index in range(np.shape(sequence)[1]):
                    fields[f"sequence_{index}"] = sequence[:, index].tolist()
                data = models.Data(fields=fields, measurement=self.configuration.measurement)
                self._data_change(data)
            except Exception as e:
                self.logger.error("Could not random data: {0}".format(str(e)),
                                  exc_info=config.EXC_INFO)
            if self.configuration.interval == 0:
                break
            # This should prevent shifting a little.
            required_time = datetime.datetime.now() - start_time
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
    description: str = "This module generates a Sobol’ sequence."
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
        The configuration model of the module.
        """
        dimensions: int = field(
            metadata=dict(description="The dimension. Defines the number of sequences included in the fields.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=0, max=21201, exclusive=False)),
            default=1)
        lower_bound: List[float] = field(
            metadata=dict(description="The lower bound (inclusive) for each dimension.",
                          required=False,
                          dynamic=False),
            default_factory=list)
        upper_bound: List[float] = field(
            metadata=dict(description="The upper bound (exclusive) for each dimension.",
                          required=False,
                          dynamic=False),
            default_factory=list)
        number: int = field(
            metadata=dict(description="The number of entries in the sequence calculated with: 2^number. "
                                      "Since the number of samples in the sequence has to be power of 2. "
                                      "E.g. number = 3 means 2^3 = 8.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=0, max=1000, exclusive=False)),
            default=6)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.
        :returns: True if the import was successful.
        """
        try:
            global scipy
            import scipy
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        sequence = stats.qmc.Sobol(self.configuration.dimensions, scramble=True).random_base2(
            m=self.configuration.number)
        if self.configuration.lower_bound and self.configuration.upper_bound:
            sequence = stats.qmc.scale(sequence, self.configuration.lower_bound, self.configuration.upper_bound)
        fields = {}
        for index in range(np.shape(sequence)[1]):
            fields[f"sequence_{index}"] = sequence[:, index].tolist()
        return fields
