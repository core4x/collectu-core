""""""
import os
from dataclasses import dataclass, field
from typing import List

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
    description: str = "This module makes a min-max-normalization (between min_value and max_value)."
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
        min_value: float = field(
            metadata=dict(description="The minimal value.",
                          required=False,
                          dyamic=False),
            default=0.0)
        lower_bound: float = field(
            metadata=dict(description="The lower limit (= min_value).",
                          required=True,
                          dyamic=True),
            default=None)
        max_value: float = field(
            metadata=dict(description="The maximal value.",
                          required=False,
                          dyamic=False),
            default=1.0)
        upper_bound: float = field(
            metadata=dict(description="The upper limit (= max_value).",
                          required=True,
                          dyamic=True),
            default=None)
        dynamic_identification_of_min_max: bool = field(
            metadata=dict(description="If the value of the key is a list and this is enabled, "
                                      "the lower and upper bound are automatically identified. "
                                      "The defined lower_bound and upper_bound are ignored.",
                          required=False,
                          dyamic=False),
            default=True)
        key: str = field(
            metadata=dict(description="The key of the value which shall be normalized. "
                                      "If '*' is given, every key of the fields and tags, "
                                      "which is of type float or int is normalized.",
                          required=False,
                          dyamic=True),
            default="*")

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
        lower_bound = self._dyn(self.configuration.lower_bound, data_type=["float", "int"])
        upper_bound = self._dyn(self.configuration.upper_bound, data_type=["float", "int"])

        if field_key == "*":
            for key, value in data.fields.copy().items():
                if type(value) in [int, float]:
                    data.fields[key] = ((self.configuration.max_value - self.configuration.min_value) * (
                            value - lower_bound) / (upper_bound - lower_bound)) + self.configuration.min_value
                elif isinstance(value, list):
                    if self.configuration.dynamic_identification_of_min_max:
                        lower_bound_temp = min(value)
                        upper_bound_temp = max(value)
                    else:
                        lower_bound_temp = lower_bound
                        upper_bound_temp = upper_bound
                    temp_value = []
                    for single_value in value:
                        temp_value.append(((self.configuration.max_value - self.configuration.min_value) * (
                                single_value - lower_bound_temp) / (
                                                   upper_bound_temp - lower_bound_temp)) + self.configuration.min_value)
                    data.fields[key] = temp_value
            for key, value in data.tags.copy().items():
                if type(value) in [int, float]:
                    data.tags[key] = ((self.configuration.max_value - self.configuration.min_value) * (
                            value - lower_bound) / (upper_bound - lower_bound)) + self.configuration.min_value
                elif isinstance(value, list):
                    if self.configuration.dynamic_identification_of_min_max:
                        lower_bound_temp = min(value)
                        upper_bound_temp = max(value)
                    else:
                        lower_bound_temp = lower_bound
                        upper_bound_temp = upper_bound
                    temp_value = []
                    for single_value in value:
                        temp_value.append(((self.configuration.max_value - self.configuration.min_value) * (
                                single_value - lower_bound_temp) / (
                                                   upper_bound_temp - lower_bound_temp)) + self.configuration.min_value)
                    data.fields[key] = temp_value
        else:
            field_value = data.fields.get(field_key, None)
            if type(field_value) in [int, float]:
                data.fields[field_key] = ((self.configuration.max_value - self.configuration.min_value) * (
                        field_value - lower_bound) / (upper_bound - lower_bound)) + self.configuration.min_value
            elif isinstance(field_value, list):
                if self.configuration.dynamic_identification_of_min_max:
                    lower_bound_temp = min(field_value)
                    upper_bound_temp = max(field_value)
                else:
                    lower_bound_temp = lower_bound
                    upper_bound_temp = upper_bound
                temp_value = []
                for single_value in field_value:
                    temp_value.append(((self.configuration.max_value - self.configuration.min_value) * (
                            single_value - lower_bound_temp) / (
                                               upper_bound_temp - lower_bound_temp)) + self.configuration.min_value)
                data.fields[field_key] = temp_value

            tag_value = data.tags.get(field_key, None)
            if type(tag_value) in [int, float]:
                data.tags[field_key] = ((self.configuration.max_value - self.configuration.min_value) * (
                        tag_value - lower_bound) / (upper_bound - lower_bound)) + self.configuration.min_value
            if isinstance(tag_value, list):
                if self.configuration.dynamic_identification_of_min_max:
                    lower_bound_temp = min(tag_value)
                    upper_bound_temp = max(tag_value)
                else:
                    lower_bound_temp = lower_bound
                    upper_bound_temp = upper_bound
                temp_value = []
                for single_value in tag_value:
                    temp_value.append(((self.configuration.max_value - self.configuration.min_value) * (
                            single_value - lower_bound_temp) / (
                                               upper_bound_temp - lower_bound_temp)) + self.configuration.min_value)
                data.fields[field_key] = temp_value

        return data
