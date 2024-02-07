"""
If the key does not exist, the data is not forwarded.

If the comparison value can be a float, integer, or boolean but should be a string, use `""` to encapsulate it:
e.g. `string == "3"`, where `string` is `"3"` - evaluates `True`,
whereby `string == 3`, where `string` is `"3"` - evaluates `False`.
"""
import os
from dataclasses import dataclass, field
from typing import List, Union, Dict, Any

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import OneOf


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module realizes an if statement for field values. " \
                       "Only if the expression is 'True', the data object is forwarded."
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
            metadata=dict(description="The field key whose value is to be compared.",
                          required=True,
                          dynamic=True),
            default=None)
        comparison_value: Union[str, float, int, bool, list] = field(
            metadata=dict(description="The value which is used for the comparison with the key value.",
                          required=True,
                          dynamic=True),
            default=None)
        operator: str = field(
            metadata=dict(description="The operator.",
                          required=False,
                          validate=OneOf(["==", ">", "<", "!=", ">=", "<="])),
            default="==")

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {"operator": ["==", ">", "<", "!=", ">=", "<="]}

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
                                                     key="test3",
                                                     comparison_value=1,
                                                     operator="=="),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test1",
                                                     comparison_value=1,
                                                     operator="!="),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={"test1": 1, "test2": 2})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test1",
                                                     comparison_value=3,
                                                     operator="<"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": 4, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={"test1": 1, "test2": 2})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test1",
                                                     comparison_value=3.3,
                                                     operator=">="),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": 4, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": 4, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}

        test_data = [test_1, test_2, test_3, test_4]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        value = data.fields.get(str(self._dyn(self.configuration.key)), None)
        comparison_value = self._dyn(self.configuration.comparison_value)

        result: bool = True
        if value is None:
            result = False
        elif not eval(str(value) + self.configuration.operator + str(comparison_value),
                      {value: value, comparison_value: comparison_value}):
            result = False

        if not result:
            data.fields = {}

        return data
