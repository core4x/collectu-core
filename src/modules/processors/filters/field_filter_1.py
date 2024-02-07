"""
**Note:**   We compare lowered strings and not the actual data type.
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
    description: str = "This module filters received data according to the given field key and field value."
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
        field_key: str = field(
            metadata=dict(description="The field key which shall be passed (if invert is false). "
                                      "If invert is true, the field is excluded from the passed data. "
                                      "NOT case sensitive.",
                          required=True,
                          dynamic=True),
            default=None)
        field_value: str = field(
            metadata=dict(description="The field value which has to match. "
                                      "If '*' is given, only the field key is considered.",
                          required=False,
                          dynamic=True),
            default="*")
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
                                                     field_key="test3",
                                                     field_value="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     field_key="test3",
                                                     field_value="1"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1},
                                             tags={"test1": 1, "test2": 2})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     field_key="test3",
                                                     field_value="1"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 12, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={"test1": 1, "test2": 2})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     field_key="test",
                                                     field_value="*"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 12, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={"test1": 1, "test2": 2})}
        test_5 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     field_key="test3",
                                                     field_value="*",
                                                     invert=True),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 12, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_6 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     field_key="test3",
                                                     field_value="12",
                                                     invert=True),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 12, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}

        test_data = [test_1, test_2, test_3, test_4, test_5, test_6]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        fields = {}
        for key, value in data.fields.items():
            # Check if field exists.
            if not self.configuration.invert:
                if key.lower() == str(self._dyn(self.configuration.field_key)).lower():
                    # If only the existence of the key matters.
                    if str(self._dyn(self.configuration.field_value)) == '*':
                        fields[key] = value
                    # If also the value has to match the user input.
                    elif str(value).lower() == str(self._dyn(self.configuration.field_value)).lower():
                        fields[key] = value
            else:
                if key.lower() != str(self._dyn(self.configuration.field_key)).lower():
                    fields[key] = value
                else:
                    if self.configuration.field_value == '*':
                        pass
                    elif str(value).lower() != str(self._dyn(self.configuration.field_value)).lower():
                        fields[key] = value
        data.fields = fields
        return data
