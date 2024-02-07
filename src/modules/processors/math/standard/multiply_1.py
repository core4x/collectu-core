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
    description: str = "This module multiplies key and tag values with a defined value."
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
        factor: float = field(
            metadata=dict(description="The multiplication factor.",
                          required=False,
                          dynamic=True),
            default="")
        key: str = field(
            metadata=dict(description="The field or tag key whose value shall be multiplied. "
                                      "Value has to be int or float. "
                                      "If '*' is given, every int and float value is multiplied.",
                          required=False,
                          dynamic=True),
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
                                                     factor=-1,
                                                     key="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 3.5},
                                            tags={"test1": True, "test2": "2"}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": -1, "test4": -3.5},
                                             tags={"test1": True, "test2": "2"})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     factor=2.0,
                                                     key="test3"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 3.567},
                                            tags={"test1": 10, "test2": 2.123}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 2, "test4": 3.567},
                                             tags={"test1": 10, "test2": 2.123})}
        test_data = [test_1, test_2]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        key = self._dyn(self.configuration.key)
        if key != "*":
            # Check if key is in data object.
            if data.fields.get(key, False):
                if isinstance(data.fields.get(key), (int, float)) and not isinstance(data.fields.get(key), bool):
                    data.fields[key] = data.fields.get(key) * self.configuration.factor
            if data.tags.get(key, False):
                if isinstance(data.tags.get(key), (int, float)) and not isinstance(data.tags.get(key), bool):
                    data.tags[key] = data.tags.get(key) * self.configuration.factor
        else:
            for key, value in data.fields.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    data.fields[key] = value * self.configuration.factor
            for key, value in data.tags.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    data.tags[key] = value * self.configuration.factor
        return data
