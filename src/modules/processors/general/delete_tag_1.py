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
    description: str = "This module deletes the field with the given key and optional given value."
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
        tag_key: str = field(
            metadata=dict(description="The tag key which shall be deleted.",
                          required=True,
                          dynamic=True),
            default=None)
        tag_value: str = field(
            metadata=dict(description="The tag value which has to match. "
                                      "If '*' is given, only the tag key is considered.",
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
                                                     tag_key="test1",
                                                     tag_value="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_key="test1",
                                                     tag_value="1"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test2": 2})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_key="test1",
                                                     tag_value="1"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 12, "test4": 1.234},
                                            tags={"test1": 12, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 12, "test4": 1.234},
                                             tags={"test1": 12, "test2": 2})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_key="test",
                                                     tag_value="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 12, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 12, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}

        test_data = [test_1, test_2, test_3, test_4]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        for key, value in data.tags.copy().items():
            # Check if field exists.
            if key == self._dyn(self.configuration.tag_key):
                # If only the existence of the key matters.
                if self._dyn(self.configuration.tag_value) == '*':
                    data.tags.pop(key)
                # If also the value has to match the user input.
                elif str(value) == self._dyn(self.configuration.tag_value):
                    data.tags.pop(key)
        return data
