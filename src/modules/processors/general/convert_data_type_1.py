""""""
import os
from dataclasses import dataclass, field
from typing import Any, List

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import Validation, ValidationError


class DataTypeValidation(Validation):
    """
    Checks if the given data types are valid.
    """

    def validate(self, field_name: str, value: Any):
        """
        Called by the __post_init__ of the model.

        Raises a ValidationError with error messages as list if the validation was not successful.

        :param field_name: The field name.
        :param value: The value of the field.
        """
        errors = []
        # Remove white space and split if it is a list separated with ';'.
        field_value_type = value.replace(" ", "").split(";")

        known_types = {'int': int,
                       'float': float,
                       'bool': bool,
                       'str': str,
                       'list': list}
        types = []
        for type_value in field_value_type:
            real_type = known_types.get(type_value, None)
            if real_type:
                types.append(real_type)
            else:
                errors.append(f"'{type_value}' is not a valid field value type. "
                              "Available types are: str, bool, int, float, or list.")
        if not types:
            errors.append(f"No valid field value types were given: ('{field_value_type}').")
        if errors:
            raise ValidationError(errors)


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module tries to convert the data type of the value."
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
            metadata=dict(description="The field/tag key of the value which will be tried to be converted. "
                                      "If '*' is given, every field and tag value is tried to be converted.",
                          required=False,
                          dynamic=True),
            default="*")
        data_type: str = field(
            metadata=dict(description="The field/tag data type, used for conversion. "
                                      "Available types are: str, bool, int, float, or list. "
                                      "You can also define multiple types "
                                      "separated with ';' e.g.: float;int.",
                          required=False,
                          validate=DataTypeValidation()),
            default="float")

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
                                                     key="*",
                                                     data_type="int;float"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="*",
                                                     data_type="int"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": "1", "test2": True},
                                            tags={}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": 1, "test2": 1},
                                             tags={})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test1",
                                                     data_type="int"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": "1"},
                                            tags={"test2": 3}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": 1},
                                             tags={"test2": 3})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test1",
                                                     data_type="bool"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": True},
                                            tags={"test3": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": True},
                                             tags={"test3": 2})}
        test_5 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="*",
                                                     data_type="bool"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test1": True},
                                            tags={"test3": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test1": True},
                                             tags={"test3": True})}
        test_6 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test4",
                                                     data_type="int;float", ),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": "1", "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": "1", "test4": 1},
                                             tags={"test1": 1, "test2": 2})}
        test_7 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test4",
                                                     data_type="int;float"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": "1", "test4": "string"},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": "1", "test4": "string"},
                                             tags={"test1": 1, "test2": 2})}
        test_8 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="*",
                                                     data_type="list"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": "1"},
                                            tags={}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": ["1"]},
                                             tags={})}
        test_data = [test_1, test_2, test_3, test_4, test_5, test_6, test_7, test_8]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        # Remove white space and split if it is a list separated with ';'.
        data_type = self.configuration.data_type.replace(" ", "").split(";")

        known_types = {'int': int,
                       'float': float,
                       'bool': bool,
                       'str': str,
                       'list': list}

        types = []
        for data_type_value in data_type:
            real_type = known_types.get(data_type_value, None)
            if real_type:
                types.append(real_type)

        def _check(dict_to_be_checked: dict):
            checked_keys = {}
            for key, value in dict_to_be_checked.items():
                if str(self._dyn(self.configuration.key)) == '*' or key.lower() == str(
                        self._dyn(self.configuration.key)).lower():
                    # Try to convert.
                    converted = False
                    for real_type in types:
                        try:
                            value = real_type(value)
                            checked_keys[key] = value
                            converted = True
                            break
                        except Exception as e:
                            pass
                    if not converted:
                        # Keep the original one.
                        checked_keys[key] = value
                else:
                    checked_keys[key] = value
            return checked_keys

        data.fields = _check(data.fields)
        data.tags = _check(data.tags)

        return data
