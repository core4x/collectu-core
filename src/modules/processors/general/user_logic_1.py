"""
You can copy your code in the raw configuration file.
For doing so, use a yaml compatible multiline string as shown below.

Example:

logic: |
        if data.fields.get("Laser_Pulse_repetition_rate_kHz") == 200:
            data.tags["Just an example"] = "nice"
"""
import math  # Imported if the user wants to use math functions.
import os
from dataclasses import dataclass, field
from typing import List, Any
import ast

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import Validation, ValidationError


class PythonCodeValidation(Validation):
    """
    Checks if the given code is valid.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module executes user code written in python."
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

    def validate(self, field_name: str, value: Any):
        """
        Called by the __post_init__ of the model.

        Raises a ValidationError with error messages as list if the validation was not successful.

        :param field_name: The field name.
        :param value: The value of the field.
        """
        errors = []
        try:
            ast.parse(value)
        except SyntaxError as e:
            errors.append("The given logic is not a valid python code: {0}".format(str(e)))
            raise ValidationError(errors)


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        logic: str = field(
            metadata=dict(description="The code written in python. "
                                      "The data object can be accessed and manipulated using `data`.",
                          required=True,
                          dynamic=True,
                          validate=PythonCodeValidation()),
            default=None)

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
                                                     logic="if data.fields:\n"
                                                           "\tdata.fields = {}\n"
                                                           "else:\n"
                                                           "\tdata.tags = {}\n"),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     logic="if data.fields:\n"
                                                           "\tdata.fields = {}\n"
                                                           "else:\n"
                                                           "\tdata.tags = {}\n"),
                  "input_data": models.Data(measurement="test",
                                            fields={},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={},
                                             tags={})}

        test_data = [test_1, test_2]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        exec(self._dyn(self.configuration.logic))
        return data
