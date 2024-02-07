"""
**Note:** The data type `list` generates a list of strings and integers.
"""
from dataclasses import dataclass, field
import datetime
import time
from threading import Thread
from typing import Dict, Any
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
__description__: str = "This module generates random field entries of defined data type."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = []
"""Define your requirements here."""


def _generate_random_value(data_type: str):
    """
    Generates random data.

    :param data_type: The data type of the value to be generated.
    """
    if data_type == "str":
        return ''.join(random.choice(string.ascii_letters + string.digits) for i in range(10))
    if data_type == "int":
        return random.randint(0, 100)
    if data_type == "float":
        return random.random()
    if data_type == "bool":
        return bool(random.getrandbits(1))
    if data_type == "list":
        string_list = [random.choice(string.ascii_letters + string.digits) for i in range(10)]
        integer_list = list(map(int, random.sample(range(10, 30), 20)))
        return string_list + integer_list


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
    description: str = "This module generates random field entries of defined data type in a defined interval."
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
        key: str = field(
            metadata=dict(description="The key.",
                          dynamic=True,
                          required=False),
            default=''.join(random.choice(string.ascii_letters + string.digits) for i in range(10)))
        data_type: str = field(
            metadata=dict(
                description="Data type of the value. Available data types are: bool, str, int, float, and list. ",
                required=False,
                validate=OneOf(['str', 'bool', 'int', 'float', 'list'])),
            default="str")
        interval: float = field(
            metadata=dict(description="Interval in seconds in which the module generates test data. "
                                      "If the interval is 0, it is only executed once.",
                          required=False,
                          validate=Range(min=0, max=1000, exclusive=False)),
            default=1)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {
            "data_type": ['str', 'bool', 'int', 'float', 'list']
        }

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
                fields = {self._dyn(self.configuration.key): _generate_random_value(self.configuration.data_type)}
                data = models.Data(fields=fields, measurement=self.configuration.measurement)
                self._data_change(data)
            except Exception as e:
                self.logger.error("Could not generate test data: {0}".format(str(e)),
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
    description: str = "This module generates random field entries of defined data type if requested."
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
        key: str = field(
            metadata=dict(description="The key.",
                          dynamic=True,
                          required=False),
            default=''.join(random.choice(string.ascii_letters + string.digits) for i in range(10)))
        data_type: str = field(
            metadata=dict(
                description="Data type of the value. Available data types are: bool, str, int, float, and list. ",
                required=False,
                validate=OneOf(['str', 'bool', 'int', 'float', 'list'])),
            default="str")

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {
            "data_type": ['str', 'bool', 'int', 'float', 'list']
        }

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        return {self._dyn(self.configuration.key): _generate_random_value(self.configuration.data_type)}
