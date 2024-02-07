"""
**Note:**   Please make sure the data type of the variable value matches the specified variable type!

Please provide a list of fields.

**Note:**   When you are configuring a tag module, `is_field` is not required on field level.
            You can just set it on the module level (`is_tag` or `is_field`).

The field object looks like the following:

| Required | Parameter | Description | Data Type | Default | Dynamic |
|:--------:|:----------| :-----------|:----------|:--------|:--------|
| x | key | The key of the field/tag. Please make sure, that every key exists only once for one input module. | str | | |
| | value | The (default) value of the field/tag. Please make sure, the value data type matches the data_type parameter. The type of this value is used for generating the frontend elements. You can also pass a list of values (e.g.: [1, 2, 3]), which will generate a drop down menu. | Union[str, float, int, bool, list] | Your Input | |
| | is_field | Is the variable a field. If false, it is a tag. | bool | True | |
| | editable | Is the field/tag value editable. | bool | True | |
| | data_type | Data type of the value. Available data types are: bool, str, int, float. If you pass a list, please make sure all values are of this data type. | str | str | |

> Tag modules return the last received input.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Union, List

# Internal imports.
import config
from models.validations import OneOf, Range, validate_module, NestedListClassValidation
from modules.base.base import send_data
from modules.inputs.base.base import AbstractVariableModule, AbstractTagModule, models

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = True
"""Is this module public?"""
__description__: str = "This module collects user input from the frontend."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = []
"""Define your requirements here."""


@dataclass
class Field:
    """
    The configuration of a single field.
    """
    key: str = field(
        metadata=dict(description="The key of the field/tag. Please make sure, that every key exists only once "
                                  "for one input module.",
                      required=True,
                      dynamic=True),
        default=None)
    value: Union[str, float, int, bool, list] = field(
        metadata=dict(description="The (default) value of the field/tag. "
                                  "Please make sure, the value data type matches the data_type parameter. "
                                  "The type of this value is used for generating the frontend elements. "
                                  "You can also pass a list of values (e.g.: [1, 2, 3]), "
                                  "which will generate a drop down menu.",
                      required=False,
                      dynamic=True),
        default="Your input")
    is_field: bool = field(
        metadata=dict(description="Is the variable a field. If false, it is a tag. Only for .variable modules.",
                      required=False,
                      dynamic=True),
        default=True)
    editable: bool = field(
        metadata=dict(description="Is the field/tag value editable.",
                      required=False,
                      dynamic=True),
        default=True)
    data_type: str = field(
        metadata=dict(description="Data type of the value. Available data types are: bool, str, int, float. "
                                  "If you pass a list, please make sure all values are of this data type.",
                      required=False,
                      dynamic=True,
                      validate=OneOf(['str', 'bool', 'int', 'float'])),
        default="str")

    def __post_init__(self):
        validate_module(self)


class VariableModule(AbstractVariableModule):
    """
    A variable module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module forwards user input from the frontend."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        title: str = field(
            metadata=dict(description="The title of the user input element.",
                          required=False),
            default="User Input")
        fields: List[Field] = field(
            metadata=dict(description="The list of fields for this user input module. Example: "
                                      '{"key": "test", "value": ["choice 1", "choice 2"], "is_field": true, '
                                      '"editable": true, "data_type": "str"}',
                          required=False,
                          dynamic=True,
                          validate=NestedListClassValidation(child_class=Field, child_field_name="fields")),
            default_factory=list)

        def __post_init__(self):
            super().__post_init__()
            fields = []
            for field_dict in self.fields:
                fields.append(Field(**field_dict))
            setattr(self, "fields", fields)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {
            "data_type": ['str', 'bool', 'int', 'float']
        }

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.
        VariableModules normally start a subscription.

        :returns: True if successfully connected, otherwise false.
        """
        return True

    def store_data(self, data: models.Data):
        """
        This method is called by the frontend to store user input.

        :param data: The data object from the frontend.
        """
        self._data_change(data)

    @send_data
    def _data_change(self, data: models.Data):
        """
        Is just called by the _data_change function.
        """
        return data


class TagModule(AbstractTagModule):
    """
    A tag module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module adds the last received user input from the frontend if requested."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.TagModule):
        """
        The configuration model of the module.
        """
        title: str = field(
            metadata=dict(description="The title of the user input element.",
                          required=False),
            default="User Input")
        fields: List[Field] = field(
            metadata=dict(description="The list of tags for this user input module. Example: "
                                      '{"key": "test", "value": ["choice 1", "choice 2"], "is_field": true, '
                                      '"editable": true, "data_type": "str"}',
                          required=False,
                          dynamic=True,
                          validate=NestedListClassValidation(child_class=Field, child_field_name="fields")),
            default_factory=list)
        use_default_value: bool = field(
            metadata=dict(description="If the user has not submitted any data, the default values are used. "
                                      "Otherwise, the data object is not forwarded.",
                          required=False),
            default=True)

        def __post_init__(self):
            super().__post_init__()
            fields = []
            for field_dict in self.fields:
                fields.append(Field(**field_dict))
            setattr(self, "fields", fields)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        self.last_fields = {}
        """The last received fields."""

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {
            "data_type": ['str', 'bool', 'int', 'float']
        }

    def store_data(self, data: models.Data):
        """
        This method is called by the frontend to store user input.

        :param data: The data object from the frontend.
        """
        self.last_fields = data.fields

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        if not self.last_fields and self.configuration.use_default_value:
            default_data = {}
            for field in self.configuration.fields:
                if isinstance(field.value, list):
                    default_data[field.key] = next(iter(field.value), None)
                else:
                    default_data[field.key] = field.value

            return default_data
        else:
            # Return empty or regular object.
            return self.last_fields
