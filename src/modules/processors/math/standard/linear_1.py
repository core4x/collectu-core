""""""
from dataclasses import dataclass, field
from typing import List
import math

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module applies a linear function on the given key values."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    field_requirements: list[str] = []
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        key: str = field(
            metadata=dict(description="The key of the value which shall be calculated. "
                                      "If '*' is given, every key of the fields and tags, "
                                      "which is of type float, int or list (with int and float) is taken.",
                          required=False,
                          dyamic=True),
            default="*")
        x1: float = field(
            metadata=dict(description="The x1 parameter. (y2 -y1) / (x2 -x1) * value + (x2 * y1 - x1 * y2) / (x2 - x1)",
                          required=True,
                          dyamic=False),
            default=None)
        y1: float = field(
            metadata=dict(description="The y1 parameter. (y2 -y1) / (x2 -x1) * value + (x2 * y1 - x1 * y2) / (x2 - x1)",
                          required=False,
                          dyamic=False),
            default=-1.0)
        x2: float = field(
            metadata=dict(description="The x2 parameter. (y2 -y1) / (x2 -x1) * value + (x2 * y1 - x1 * y2) / (x2 - x1)",
                          required=True,
                          dyamic=False),
            default=None)
        y2: float = field(
            metadata=dict(description="The y2 parameter. (y2 -y1) / (x2 -x1) * value + (x2 * y1 - x1 * y2) / (x2 - x1)",
                          required=False,
                          dyamic=False),
            default=1.0)
        result_key_name: str = field(
            metadata=dict(description="The key of the result. Is only used if a special key is selected. "
                                      "Otherwise, the key value is overwritten.",
                          required=False,
                          dynamic=False),
            default="result")

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    @classmethod
    def get_test_data(cls) -> List[dict]:
        """
        Provides the test data for processor modules.
        Not every processor modules provides test data.
        The validation functionality is skipped.

        :returns: A list containing test data with the keys:
                  module_config: The configuration of the module as yaml string.
                  input_data: The input data object with measurement, fields and tags.
                  output_data: The expected output data object with measurement, fields and tags.
        """
        test_data = []
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        # Get dynamic variable.
        field_key = self._dyn(self.configuration.key)

        def linear(x):
            return (self.configuration.y2 - self.configuration.y1) / (
                    self.configuration.x2 - self.configuration.x1) * x + (
                           self.configuration.x2 * self.configuration.y1 - self.configuration.x1 * self.configuration.y2) / (
                           self.configuration.x2 - self.configuration.x1)

        if field_key == "*":
            for key, value in data.fields.copy().items():
                # Check if it is of type float, int or list.
                if isinstance(value, float) or isinstance(value, int):
                    data.fields[key] = linear(value)
                elif isinstance(value, list):
                    temp_values = []
                    for single_value in value:
                        if isinstance(single_value, float) or isinstance(single_value, int):
                            temp_values.append(linear(single_value))
                    data.fields[key] = temp_values
            for key, value in data.tags.copy().items():
                # Check if it is of type float, int or list.
                if isinstance(value, float) or isinstance(value, int):
                    data.fields[key] = linear(value)
                elif isinstance(value, list):
                    temp_values = []
                    for single_value in value:
                        if isinstance(single_value, float) or isinstance(single_value, int):
                            temp_values.append(linear(single_value))
                    data.fields[key] = temp_values
        else:
            value = data.fields.get(field_key, None)
            # Check if it is of type float, int or list.
            if isinstance(value, float) or isinstance(value, int):
                data.fields[self.configuration.result_key_name] = linear(value)
            elif isinstance(value, list):
                temp_values = []
                for single_value in value:
                    if isinstance(single_value, float) or isinstance(single_value, int):
                        temp_values.append(linear(single_value))
                data.fields[self.configuration.result_key_name] = temp_values
        return data
