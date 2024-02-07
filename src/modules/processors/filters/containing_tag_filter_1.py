"""
Only if the tag with the given key (and optional the given value) is contained, the complete data object is passed.
"""
import os
from dataclasses import dataclass, field
from typing import List, Union

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
    description: str = "This module filters received data according to the given tag key and tag value."
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
            metadata=dict(description="The tag key which shall be filtered. Case sensitive.",
                          required=True,
                          dynamic=True),
            default=None)
        tag_value: Union[str, int, float, bool, list] = field(
            metadata=dict(description="The tag value which has to match. Case sensitive. "
                                      "If '*' is given, only the tag key is considered.",
                          required=False,
                          dynamic=True),
            default="*")
        contains: bool = field(
            metadata=dict(description="Boolean indicating if the tag key "
                                      "(and optional tag value) has to be contained or not. "
                                      "Means, if contains is `True`, everything is "
                                      "passed if it contains the key (and value). If `False`, "
                                      "every object NOT containing the tag is passed.",
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
                                                     tag_key="test1"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_key="test1"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test2": 1},
                                            tags={}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_key="test2",
                                                     tag_value=3),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": 1},
                                            tags={"test2": 3}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": 1},
                                             tags={"test2": 3})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_key="test3",
                                                     tag_value=3,
                                                     contains=True),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": 3},
                                            tags={"test3": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={})}
        test_5 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     tag_key="test4",
                                                     tag_value=123,
                                                     contains=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": 3, "test3": 2},
                                            tags={"test4": 123}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={})}
        test_data = [test_1, test_2, test_3, test_4, test_5]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        tag_exists = False
        for key, value in data.tags.items():
            # Check if key exists.
            if key == self._dyn(self.configuration.tag_key):
                # If only the existence of the key matters.
                if self._dyn(self.configuration.tag_value) == '*':
                    tag_exists = True
                    break
                # If also the value has to match the user input.
                elif value == self._dyn(self.configuration.tag_value):
                    tag_exists = True
                    break

        if self.configuration.contains:
            if not tag_exists:
                # When 'contains' is True, every object containing the tag shall be passed.
                data.fields = {}
                data.tags = {}
        else:
            # When 'contains' is False, every object not containing the tag shall be passed.
            if tag_exists:
                data.fields = {}
                data.tags = {}
        return data
