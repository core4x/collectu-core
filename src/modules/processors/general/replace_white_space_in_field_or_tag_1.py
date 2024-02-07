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
    description: str = "This module replaces white space in field or tag keys."
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
            metadata=dict(description="The key which shall be renamed. "
                                      "If '*' is given, every field and tag key is processed.",
                          required=False,
                          dynamic=True),
            default="*")
        new: str = field(
            metadata=dict(description="The new string to be inserted.",
                          required=False,
                          dynamic=False),
            default="_")

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
                                                     key="test 1",
                                                     new=""),
                  "input_data": models.Data(measurement="test",
                                            fields={"test 1": 1, "test4": 1.234},
                                            tags={"test 1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": 1, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="*",
                                                     new=""),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}

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
            if data.fields.get(key, None) is not None:
                new_key = key.replace(" ", self.configuration.new)
                if new_key != key:
                    data.fields[new_key] = data.fields.get(key)
                    del data.fields[key]
            if data.tags.get(key, None) is not None:
                new_key = key.replace(" ", self.configuration.new)
                if new_key != key:
                    data.tags[new_key] = data.tags.get(key)
                    del data.tags[key]
        else:
            for key, value in data.fields.copy().items():
                new_key = key.replace(" ", self.configuration.new)
                if new_key != key:
                    data.fields[new_key] = value
                    del data.fields[key]
            for key, value in data.tags.copy().items():
                new_key = key.replace(" ", self.configuration.new)
                if new_key != key:
                    data.tags[new_key] = value
                    del data.tags[key]

        return data
