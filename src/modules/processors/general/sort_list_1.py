""""""
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
    description: str = "This module sorts the values (if they are float or int) of a given list."
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
            metadata=dict(description="The key of the value which shall be sorted. "
                                      "If '*' is given, every key of the fields and tags, "
                                      "which is of type list (and their values are float or int) is taken.",
                          required=False,
                          dyamic=True),
            default="*")
        reverse: bool = field(
            metadata=dict(description="Reverse the sorting. True will sort the list descending.",
                          required=False,
                          dyamic=False),
            default=False)

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

        if field_key == "*":
            for key, value in data.fields.copy().items():
                # Check if it is of type list.
                if isinstance(value, list):
                    # Check if all values are of type int or float.
                    if all(type(n) in [float, int] for n in value):
                        data.fields[key].sort(reverse=self.configuration.reverse)
            for key, value in data.tags.copy().items():
                # Check if it is of type list.
                if isinstance(value, list):
                    # Check if all values are of type int or float.
                    if all(type(n) in [float, int] for n in value):
                        data.tags[key].sort(reverse=self.configuration.reverse)
        else:
            value = data.fields.get(field_key, None)
            if isinstance(value, list):
                # Check if all values are of type int or float.
                if all(type(n) in [float, int] for n in value):
                    data.fields[field_key].sort(reverse=self.configuration.reverse)
        return data
