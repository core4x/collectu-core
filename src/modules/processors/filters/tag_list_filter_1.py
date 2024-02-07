"""
**Note:**   We compare lowered strings.
"""
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
    description: str = "This module filters received data according to the given tag keys."
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
        tag_keys: List[str] = field(
            metadata=dict(description="The tag keys which shall be passed (if invert is false). "
                                      "If invert is true, the tag is excluded from the passed data.",
                          required=True),
            default=None)
        invert: bool = field(
            metadata=dict(description="Invert the filtering.",
                          required=False),
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
        test_1 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_keys=["test1", "test2"]),
                  "input_data": models.Data(measurement="test",
                                                       fields={"test3": 1, "test4": 1.234},
                                                       tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                                        fields={"test3": 1, "test4": 1.234},
                                                        tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_keys=["test1"]),
                  "input_data": models.Data(measurement="test",
                                                       fields={"test3": 1, "test4": 1.234},
                                                       tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                                        fields={"test3": 1, "test4": 1.234},
                                                        tags={"test1": 1})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_keys=["test2"]),
                  "input_data": models.Data(measurement="test",
                                                       fields={"test3": 12, "test4": 1.234},
                                                       tags={"test1": 12}),
                  "output_data": models.Data(measurement="test",
                                                        fields={"test3": 12, "test4": 1.234},
                                                        tags={})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_keys=["test3"],
                                                     invert=True),
                  "input_data": models.Data(measurement="test",
                                                       fields={"test3": 12, "test4": 1.234},
                                                       tags={"test3": 12, "test4": 1.234}),
                  "output_data": models.Data(measurement="test",
                                                        fields={"test3": 12, "test4": 1.234},
                                                        tags={"test4": 1.234})}
        test_data = [test_1, test_2, test_3, test_4]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        tags = {}
        for key, value in data.tags.items():
            # Check if tag exists.
            if key.lower() in [key_element.lower() for key_element in self.configuration.tag_keys]:
                if not self.configuration.invert:
                    tags[key] = value
            elif self.configuration.invert:
                tags[key] = value
        data.tags = tags
        return data
