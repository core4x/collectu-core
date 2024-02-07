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
    description: str = "This module applies the linear norm function on the given key values."
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
        result_key_name: str = field(
            metadata=dict(description="The key of the result. Can only be used if a special key is selected.",
                          required=False,
                          dynamic=False),
            default="result")
        lower: float = field(
            metadata=dict(description="The lower bound.",
                          required=False,
                          dyamic=False),
            default=1.0)
        upper: float = field(
            metadata=dict(description="The upper bound.",
                          required=False,
                          dyamic=False),
            default=1.0)

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

        def linear_norm(value):
            return (value-self.configuration.lower)/(self.configuration.upper-self.configuration.lower)

        if field_key == "*":
            # Fields.
            for key, value in data.fields.copy().items():
                # Check if it is of type float, int or list.
                if isinstance(value, float) or isinstance(value, int):
                    data.fields[key] = linear_norm(value)
                elif isinstance(value, list):
                    temp_values = []
                    for single_value in value:
                        if isinstance(single_value, float) or isinstance(single_value, int):
                            temp_values.append(linear_norm(single_value))
                    data.fields[key] = temp_values
            # Tags.
            for key, value in data.tags.copy().items():
                # Check if it is of type float, int or list.
                if isinstance(value, float) or isinstance(value, int):
                    data.fields[key] = linear_norm(value)
                elif isinstance(value, list):
                    temp_values = []
                    for single_value in value:
                        if isinstance(single_value, float) or isinstance(single_value, int):
                            temp_values.append(linear_norm(single_value))
                    data.fields[key] = temp_values

        else:
            # Selected key.
            value = data.fields.get(field_key, None)
            # Check if it is of type float, int or list.
            if isinstance(value, float) or isinstance(value, int):
                data.fields[self.configuration.result_key_name] = linear_norm(value)
            elif isinstance(value, list):
                temp_values = []
                for single_value in value:
                    if isinstance(single_value, float) or isinstance(single_value, int):
                        temp_values.append(linear_norm(single_value))
                data.fields[self.configuration.result_key_name] = temp_values
        return data
