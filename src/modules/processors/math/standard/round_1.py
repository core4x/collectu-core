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
    description: str = "This module rounds the received value(s) to the specified number of decimals."
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
        digits: int = field(
            metadata=dict(description="The number of decimals to use when rounding the number.",
                          required=False,
                          dyamic=True),
            default=0)
        key: str = field(
            metadata=dict(description="The key of the value which shall be rounded. "
                                      "If '*' is given, every key of the fields and tags, "
                                      "which is of type float or int is rounded.",
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
        test_1 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     digits=1,
                                                     key="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 3.567},
                                            tags={"test1": 1, "test2": 2.123}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 3.6},
                                             tags={"test1": 1, "test2": 2.1})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     digits=4,
                                                     key="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": "1", "test4": 3.567},
                                            tags={"test1": 10, "test2": 2.123}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": "1", "test4": 3.567},
                                             tags={"test1": 10, "test2": 2.123})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     digits=2,
                                                     key="test4"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": "1", "test4": 3.567},
                                            tags={"test1": 10, "test4": 2.123}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": "1", "test4": 3.57},
                                             tags={"test1": 10, "test4": 2.12})}
        test_data = [test_1, test_2, test_3]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.
        :returns: The data object after processing.
        """
        # Get dynamic variable.
        field_key = self._dyn(self.configuration.key)
        digits = int(self._dyn(self.configuration.digits))

        if field_key == "*":
            for key, value in data.fields.items():
                if type(value) in [int, float]:
                    data.fields[key] = round(value, digits)
            for key, value in data.tags.items():
                if type(value) in [int, float]:
                    data.tags[key] = round(value, digits)
        else:
            field_value = data.fields.get(field_key, None)
            if field_value:
                data.fields[field_key] = round(field_value, digits)

            tag_value = data.tags.get(field_key, None)
            if tag_value:
                data.tags[field_key] = round(tag_value, digits)

        return data
