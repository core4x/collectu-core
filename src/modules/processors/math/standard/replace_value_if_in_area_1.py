"""
The first area found is applied. If the value was changed, the other areas are not checked.
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import validate_module, NestedListClassValidation, ValidationError


@dataclass
class Area:
    """
    The configuration of a single area.
    """
    lower_limit: Optional[float] = field(
        metadata=dict(description="The lower limit of the area. If the key value is greater then the lower_limit, "
                                  "(and smaller then the upper_limit - if defined) "
                                  "the value is replaced with the new_value.",
                      required=False,
                      dynamic=True),
        default=None)
    upper_limit: Optional[float] = field(
        metadata=dict(description="The upper limit of the area. If the key value is smaller then the upper_limit, "
                                  "(and bigger then the lower_limit - if defined) "
                                  "the value is replaced with the new_value.",
                      required=False,
                      dynamic=True),
        default=None)
    new_value: float = field(
        metadata=dict(description=".",
                      required=False,
                      dynamic=True),
        default=1.0)

    def __post_init__(self):
        # Make custom validation in order to check if one of the two limits was defined.
        if not self.lower_limit and not self.upper_limit:
            raise ValidationError(["Either the upper or lower limit has to be defined."])
        validate_module(self)


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "Replace a key value if it is in a defined range."
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
            metadata=dict(description="The field key whose value is to be manipulated. "
                                      "If '*' is given, every field value of type int or float is checked.",
                          required=False,
                          dynamic=True),
            default="*")
        areas: List[Area] = field(
            metadata=dict(description="The list of areas. Example: "
                                      '{"lower_limit": -10, "upper_limit": 10, "new_value": 0}',
                          required=False,
                          validate=NestedListClassValidation(child_class=Area, child_field_name="areas")),
            default_factory=list)

        def __post_init__(self):
            super().__post_init__()
            areas = []
            for area_dict in self.areas:
                areas.append(Area(**area_dict))
            setattr(self, "areas", areas)

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
                                                     key="test3",
                                                     areas=[{"lower_limit": -10, "upper_limit": 10, "new_value": 0}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 0, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test3",
                                                     areas=[{"lower_limit": -10, "upper_limit": 10, "new_value": 0}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": -20, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": -20, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test3",
                                                     areas=[{"lower_limit": -10, "upper_limit": 10, "new_value": 1}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 100, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 100, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test3",
                                                     areas=[{"upper_limit": 10, "new_value": 0}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 100, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 100, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_5 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test3",
                                                     areas=[{"upper_limit": 100, "new_value": 0}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1000, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1000, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_6 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test3",
                                                     areas=[{"lower_limit": 100, "new_value": 0}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 10, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 10, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_7 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test3",
                                                     areas=[{"lower_limit": 10, "new_value": 0},
                                                            {"upper_limit": 20, "new_value": 1}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 25, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 0, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_8 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     key="test3",
                                                     areas=[{"lower_limit": 10, "new_value": 0},
                                                            {"upper_limit": 20, "new_value": 1}]),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": [25, 30, 5, 11], "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": [0, 0, 1, 0], "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}

        test_data = [test_1, test_2, test_3, test_4, test_5, test_6, test_7, test_8]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        key = self._dyn(input_string=self.configuration.key)
        if key == "*":
            keys = data.fields.keys()
        else:
            keys = [key]
        for key in keys:
            values = []
            value = data.fields.get(key)
            if isinstance(value, list):
                values = value
                for value in values:
                    if not type(value) in [int, float]:
                        raise Exception("The given value '{0}' is not of type int or float.".format(str(value)))
            elif type(value) in [int, float]:
                values.append(value)
            else:
                raise Exception("The given value '{0}' is not of type int or float.".format(str(value)))

            for value in values:
                for area in self.configuration.areas:
                    if area.lower_limit:
                        lower_limit = self._dyn(area.lower_limit, data_type=["float", "int"])
                    else:
                        lower_limit = None
                    if area.upper_limit:
                        upper_limit = self._dyn(area.upper_limit, data_type=["float", "int"])
                    else:
                        upper_limit = None
                    if lower_limit and upper_limit:
                        if upper_limit > value > lower_limit:
                            if isinstance(data.fields[key], list):
                                data.fields[key] = [x if x != value else self._dyn(area.new_value) for x in
                                                    data.fields[key]]
                                break
                            else:
                                data.fields[key] = self._dyn(area.new_value)
                                break
                    elif lower_limit:
                        if value > lower_limit:
                            if isinstance(data.fields[key], list):
                                data.fields[key] = [x if x != value else self._dyn(area.new_value) for x in
                                                    data.fields[key]]
                                break
                            else:
                                data.fields[key] = self._dyn(area.new_value)
                                break
                    elif upper_limit:
                        if value < upper_limit:
                            if isinstance(data.fields[key], list):
                                data.fields[key] = [x if x != value else self._dyn(area.new_value) for x in
                                                    data.fields[key]]
                                break
                            else:
                                data.fields[key] = self._dyn(area.new_value)
                                break
                    else:
                        raise Exception("No valid limits defined for the given area: {0}.".format(str(area)))

        return data
