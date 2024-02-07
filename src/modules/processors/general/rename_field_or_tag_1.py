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
    description: str = "This module enables the renaming of a given key."
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
        old_key: str = field(
            metadata=dict(description="The key which shall be renamed.",
                          required=True,
                          dynamic=True),
            default=None)
        new_key: str = field(
            metadata=dict(description="The new key.",
                          required=True,
                          dynamic=True),
            default=None)
        ignore_case: bool = field(
            metadata=dict(description="If true, the case of letters is ignored.",
                          required=False),
            default=True)
        is_field: bool = field(
            metadata=dict(description="If true, check the fields for the given key.",
                          required=False),
            default=True)
        is_tag: bool = field(
            metadata=dict(description="If true, check the tags for the given key.",
                          required=False),
            default=True)

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
                                                     old_key="test1",
                                                     new_key="test11"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test11": 1, "test4": 1.234},
                                             tags={"test11": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     old_key="test123",
                                                     new_key="test11"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     old_key="Test1",
                                                     new_key="test11",
                                                     ignore_case=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     old_key="test1",
                                                     new_key="test11",
                                                     ignore_case=True,
                                                     is_tag=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}

        test_data = [test_1, test_2, test_3, test_4]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        if self.configuration.is_field:
            for key, value in data.fields.copy().items():
                if (key == self._dyn(self.configuration.old_key) and not self.configuration.ignore_case) or (
                        key.lower() == self._dyn(
                    self.configuration.old_key).lower() and self.configuration.ignore_case):
                    value = data.fields.pop(key)
                    data.fields[str(self._dyn(self.configuration.new_key))] = value
        if self.configuration.is_tag:
            for key, value in data.tags.copy().items():
                if (key == self._dyn(self.configuration.old_key) and not self.configuration.ignore_case) or (
                        key.lower() == self._dyn(
                    self.configuration.old_key).lower() and self.configuration.ignore_case):
                    value = data.tags.pop(key)
                    data.tags[str(self._dyn(self.configuration.new_key))] = value
        return data
