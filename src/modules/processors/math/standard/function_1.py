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
    description: str = "This module evaluates a given function."
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
        function: str = field(
            metadata=dict(description="An evaluable function. You can use the given keys as variables. "
                                      "E.g.: key_1 + key_2",
                          required=False,
                          dynamic=True),
            default="")
        result_key_name: str = field(
            metadata=dict(description="The key of the result.",
                          required=False,
                          dynamic=True),
            default="result")

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
                                                     function="key_0 + key_1", result_key_name="result"),
                  "input_data": models.Data(measurement="test",
                                            fields={"key_0": 12, "key_1": 3},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"key_0": 12, "key_1": 3, "result": 15},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     function="key_0 + key_1 + test1", result_key_name="result"),
                  "input_data": models.Data(measurement="test",
                                            fields={"key_0": 12, "key_1": 3},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"key_0": 12, "key_1": 3, "result": 16},
                                             tags={"test1": 1, "test2": 2})}
        test_data = [test_1, test_2]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        function = self._dyn(self.configuration.function)
        data.fields[self._dyn(self.configuration.result_key_name)] = eval(function, data.tags | data.fields)
        return data
