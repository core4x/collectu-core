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
    description: str = "This module limits values to a given range."
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
        lower_limit: float = field(
            metadata=dict(description="The lower limit.",
                          required=True,
                          dyamic=True),
            default=None)
        upper_limit: float = field(
            metadata=dict(description="The upper limit.",
                          required=True,
                          dyamic=True),
            default=None)
        key: str = field(
            metadata=dict(description="The key of the value which shall be limited. "
                                      "If '*' is given, every key of the fields and tags, "
                                      "which is of type float or int is limited.",
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
                                                     lower_limit=-10,
                                                     upper_limit=10,
                                                     key="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 11},
                                            tags={}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 10},
                                             tags={})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     lower_limit=-10,
                                                     upper_limit=10,
                                                     key="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 6},
                                            tags={"test2": -10}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 6},
                                             tags={"test2": -10})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     lower_limit=-10,
                                                     upper_limit=10,
                                                     key="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 234, "test4": "some string"},
                                            tags={"test2": -14}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 10, "test4": "some string"},
                                             tags={"test2": -10})}

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
        lower_limit = float(self._dyn(self.configuration.lower_limit))
        upper_limit = float(self._dyn(self.configuration.upper_limit))

        if field_key == "*":
            for key, value in data.fields.items():
                if type(value) in [int, float]:
                    if value <= lower_limit:
                        data.fields[key] = lower_limit
                    elif value >= upper_limit:
                        data.fields[key] = upper_limit
                    else:
                        data.fields[key] = value
            for key, value in data.tags.items():
                if type(value) in [int, float]:
                    if value <= lower_limit:
                        data.tags[key] = lower_limit
                    elif value >= upper_limit:
                        data.tags[key] = upper_limit
                    else:
                        data.tags[key] = value
        else:
            field_value = data.fields.get(field_key, None)
            if field_value is not None:
                if field_value <= lower_limit:
                    data.fields[field_key] = lower_limit
                elif field_value >= upper_limit:
                    data.fields[field_key] = upper_limit
                else:
                    data.fields[field_key] = field_value

            tag_value = data.tags.get(field_key, None)
            if tag_value is not None:
                if tag_value < lower_limit:
                    data.tags[field_key] = lower_limit
                elif tag_value > upper_limit:
                    data.tags[field_key] = upper_limit
                else:
                    data.tags[field_key] = tag_value

        return data
