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
    description: str = "This module replaces characters in field or tag values."
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
            metadata=dict(description="The key which value shall be renamed. "
                                      "If '*' is given, every field and tag key is processed.",
                          required=False,
                          dynamic=True),
            default="*")
        old: str = field(
            metadata=dict(description="The old string to be replaced.",
                          required=True,
                          dynamic=False),
            default=None)
        new: str = field(
            metadata=dict(description="The new string to be inserted.",
                          required=False,
                          dynamic=False),
            default="")

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
                                                     key="test1",
                                                     old=" ",
                                                     new=""),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": "1 1", "test4": 1.234},
                                            tags={"test1": 11, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": "11", "test4": 1.234},
                                             tags={"test1": 11, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="*",
                                                     old="s",
                                                     new=""),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": "s123", "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": "123", "test4": 1.234},
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
                old_value = data.fields.get(key)
                new_value = str(old_value).replace(self.configuration.old, self.configuration.new)
                if str(old_value) != new_value:
                    data.fields[key] = new_value
            if data.tags.get(key, None) is not None:
                old_value = data.tags.get(key)
                new_value = str(old_value).replace(self.configuration.old, self.configuration.new)
                if str(old_value) != new_value:
                    data.tags[key] = new_value
        else:
            for key, old_value in data.fields.copy().items():
                new_value = str(old_value).replace(self.configuration.old, self.configuration.new)
                if str(old_value) != new_value:
                    data.fields[key] = new_value
            for key, old_value in data.tags.copy().items():
                new_value = str(old_value).replace(self.configuration.old, self.configuration.new)
                if str(old_value) != new_value:
                    data.tags[key] = new_value

        return data
