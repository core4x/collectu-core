"""
Validations of the configuration module data.
"""
from typing import Any, get_origin, get_args, Union, Pattern, Optional
from collections import defaultdict
from abc import ABC, abstractmethod
from dataclasses import fields
import re
import ast


class ValidationError(Exception):
    """
    Base class for validation errors.
    The exception contains a list with error messages (str) and can be accessed like this: e.args[0]
    """
    pass


def validate_module(module):
    """
    Module level validations. Here, the module configuration data (e.g. data type) is checked.

    Technical debts:  We can currently only type check str, int, bool, float,
    Dict[str, str/int/bool/float], and List[str/int/bool/float].

    :param module: The module configuration (instantiated data class) to be validated.

    :raises ValidationError: with a list of errors (can be accessed using: e.args[0]).
    """
    errors = []

    # Check that the field values are of the correct data type.
    for field in fields(module):
        value = getattr(module, field.name)
        if str(value).startswith("${") and str(value).endswith("}"):
            # The complete value is a dynamic variable. We have to assume, the replacement will fit the type.
            # Make them always a string.
            setattr(module, field.name, str(value))
        elif field.type in [str, int, bool, float]:
            # We check if we can type check the field.
            # This is required, since typing types (e.g. List[], Dict[], etc.) can not be checked using isinstance.
            if not isinstance(value, field.type):
                if value is None and field.metadata.get('required', False):
                    # If value is None, but it is required, it is an error.
                    errors.append(f'Missing value for field {field.name} '
                                  f'({field.metadata.get("description", "no description")}).')
                else:
                    # Try to convert.
                    try:
                        setattr(module, field.name, field.type(value))
                    except Exception as e:
                        errors.append(f'Expected field {field.name} to be of type {field.type}. Got {value} '
                                      f'of type {type(value)} instead.')
        else:
            # It is probably a typing type.
            # Check if it is a list.
            if get_origin(field.type) == list:
                if not isinstance(value, list):
                    try:
                        # If it is just a string in list format, this will make it a list.
                        value = ast.literal_eval(value)
                    except Exception as e:
                        # If it fails, we will make a list from it.
                        value = [value]
                for field_type in get_args(field.type):
                    if field_type not in [str, int, bool, float]:
                        # Unknown data type e.g. a nested configuration. We skip the check.
                        # Nested objects are validated using NestedClassValidation.
                        continue
                    for index, item in enumerate(value):
                        if not isinstance(item, field_type):
                            # Try to convert.
                            try:
                                item = field_type(item)
                                # Replace converted item in list.
                                value[index] = item
                                # Update list.
                                setattr(module, field.name, value)
                            except Exception as e:
                                errors.append(f'Expected all values {value} of field {field.name} '
                                              f'to be of type {field_type}. '
                                              f'Got {item} of type {type(item)} instead.')
            # Check if it is a dict.
            elif get_origin(field.type) == dict:
                key_type, value_type = get_args(field.type)
                try:
                    # If it is just a string in dict format, this will make it a dict.
                    value = ast.literal_eval(value)
                except Exception as e:
                    pass
                for key, value in value.items():
                    if key_type in [str, int, bool, float]:
                        if not isinstance(key, key_type):
                            errors.append(f'Expected key of field {field.name} to be of type {key_type}. '
                                          f'Got {key} of type {type(key)} instead.')
                    else:
                        # Unknown data type.
                        pass
                    if value_type in [str, int, bool, float, list]:
                        if not isinstance(value, value_type):
                            errors.append(f'Expected value of field {field.name} with the key {key} '
                                          f'to be of type {value_type}. '
                                          f'Got {value} of type {type(value)} instead.')
                    else:
                        # Unknown data type.
                        pass
            # Check if it is typing.Any.
            elif str(field.type) == "typing.Any":
                # Every data type is accepted...
                pass
            # Check if it is typing.Union or typing.Optional (Union with None).
            elif str(get_origin(field.type)) == "typing.Union":
                known_types = []
                can_be_none = False
                for field_type in get_args(field.type):
                    if field_type in [str, int, bool, float, list]:
                        known_types.append(field_type)
                    elif field_type == type(None):  # isinstance is probably not working...
                        can_be_none = True
                if can_be_none and value is None:
                    pass
                elif type(value) not in known_types:
                    if value is None and field.metadata.get('required', False):
                        # If value is None, but it is required, it is an error.
                        errors.append(f'Missing value for field {field.name} '
                                      f'({field.metadata.get("description", "no description")}).')
                    # Try to convert using the first known data type.
                    # This is helpful for e.g.: Optional[float] if we received an integer.
                    try:
                        setattr(module, field.name, known_types[0](value))
                    except Exception as e:
                        errors.append(f'Expected field of {field.name} to be one of the types {known_types}. '
                                      f'Got {value} of type {type(value)} instead.')
            else:
                errors.append(f'Unknown field type {field.type} for field {field.name}. '
                              f'This data type is not supported and can not be checked.')

        validation_class: Validation = field.metadata.get('validate', None)
        if validation_class is not None:
            if str(value).startswith("${") and str(value).endswith("}"):
                # The complete value is a dynamic variable. We have to assume, the replacement will fit the type.
                # Make them always a string.
                setattr(module, field.name, str(value))
            else:
                try:
                    validation_class.validate(field_name=field.name, value=value)
                except ValidationError as e:
                    errors.extend(e.args[0])

    if errors:
        raise ValidationError(errors)


def validate_configuration(configuration: list[Any]) -> dict[str, list[str]]:
    """
    Configuration level validations.
    Here, the complete configuration is validated (e.g. checking if all linked ids are given).

    :param configuration: The configuration list.

    :returns: A dict containing the ids of the modules and the according error messages.
    If no id is available, a '-' is used.
    """
    import data_layer
    errors = defaultdict(list)
    """All occurred errors with the module id as key and a list of error messages as strings."""

    module_ids: list[str] = [getattr(module, "id", "-") for module in configuration]
    """A list with all configured module ids."""

    versions = defaultdict(list)
    """All module versions with the module_name as key and the list of versions as integers."""

    buffer_module = None
    """Is a buffer module defined?"""

    # Check if module ids are unique.
    for module_id in set([x for x in module_ids if module_ids.count(x) > 1]):
        errors[module_id].append("The module id is not unique.")

    for module in configuration:
        for field, value in module.__dict__.items():
            # Check if the id of the dynamic variable exist.
            if "${" in str(value) and "}" in str(value):
                # It should be a dynamic variable of the form: ${module_id.key}. Check if the id exists.
                extracted_variables = []
                """The extracted dynamic variables as str, without the markers (e.g. 'module_id.key')."""

                def _extract_variables(extracted_variables, input_string_temp: str):
                    """
                    Recursively search for variables in string.
                    """
                    start = input_string_temp.find("${")
                    if start != -1:
                        end = input_string_temp[start:].find("}")
                        if end != -1:
                            end = start + end
                    else:
                        # No end found.
                        return

                    # Check if the markers were found in the string.
                    if start != -1 and end != -1 and start < end:
                        result = input_string_temp[start + len("${"):end]
                    else:
                        # If there are no more markers, we leave this function.
                        return
                    extracted_variables.append(result)
                    new_input_string = input_string_temp.replace("${" + result + "}", '')
                    # Recursively call this function until there are no more dynamic variables.
                    _extract_variables(extracted_variables, new_input_string)

                # Make input to string to be safe and extract dynamic variables if there are.
                _extract_variables(extracted_variables, str(value))
                if extracted_variables:
                    for variable_text in extracted_variables:
                        module_id = variable_text.split('.', 1)[0]
                        if module_id not in module_ids and module_id != "local" and module_id != "env":
                            errors[getattr(module, "id", "-")].append(f"The module with the id '{module_id}' of the "
                                                                      f"dynamic variable '{value}' does not exist.")

            # Check if the input_module exists and is of the correct module type (InputModule).
            if field == "input_module":
                if not str(value) in module_ids:
                    errors[getattr(module, "id", "-")].append(f"The given input_module '{value}' does not exist.")
                else:
                    input_module = next(
                        iter([config_module for config_module in configuration if
                              value == getattr(config_module, "id", "-") and
                              getattr(config_module, "module_name", "-") ==
                              getattr(module, 'module_name', 'undefined').rstrip('.tag').rstrip('.variable')]), None)
                    if input_module is None:
                        errors[getattr(module, "id", "-")].append(
                            f"The given input_module {value} should be a "
                            f"module with the name "
                            f"{getattr(module, 'module_name', 'undefined').rstrip('.tag').rstrip('.variable')}, "
                            f"but was {next(iter([getattr(config_module, 'module_name', '-') for config_module in configuration if value == getattr(config_module, 'id', '-')]))}.")

            # Check if the link ids exist and is of the correct module type.
            # Everything except InputModule and VariableModule is allowed as link.
            if field == "links":
                if not isinstance(value, list):
                    errors[getattr(module, "id", "-")].append(f"Links have to be given as list.")
                else:
                    for module_id in value:
                        if not str(module_id) in module_ids:
                            errors[getattr(module, "id", "-")].append(f"A linked module with the id '{module_id}' "
                                                                      f"does not exist.")
                        else:
                            linked_module = next(
                                iter([module for module in configuration if module_id == getattr(module, "id", "-")]),
                                None)
                            if linked_module is None or \
                                    (getattr(linked_module, "module_name", "").startswith("inputs.") and
                                     not getattr(linked_module, "module_name", "").endswith(".tag")):
                                errors[getattr(module, "id", "-")].append(f"The given link with the id '{module_id}' "
                                                                          "can not be a link. Input and variable "
                                                                          "modules have no input port.")

        # Buffer functionality.
        if getattr(module, "is_buffer", False):
            # Only one module can be a buffer.
            if buffer_module is None:
                buffer_module = module
            else:
                errors[getattr(module, "id", "-")].append(f"The module '{buffer_module.id}' is already "
                                                          f"defined as buffer. Only one module can be a buffer.")

            # If the module is a buffer (is_buffer), check that it can be a buffer.
            output_module = data_layer.registered_modules.get(getattr(module, "module_name", "-"), None)
            if not getattr(output_module, 'can_be_buffer', False):
                errors[getattr(module, "id", "-")].append(f"The module can not be a buffer.")
            if getattr(module, "buffered", False):
                errors[getattr(module, "id", "-")].append(f"The module itself is defined as a buffer "
                                                          f"and can not be buffered.")

    for module in configuration:
        if getattr(module, "buffered", False) and buffer_module is None:
            errors[getattr(module, "id", "-")].append(f"The module shall be buffered, "
                                                      f"but no buffer module was defined.")
        # Check if modules of the same type, have the same version. If not, use the latest version.
        if getattr(module, "version", 0):
            module_name = getattr(module, 'module_name', 'undefined').rstrip('.tag').rstrip('.variable')
            versions[module_name].append(getattr(module, "version"))

    for module_name, version_list in versions.items():
        if len(set(version_list)) > 1:
            errors["-"].append(f"Your configuration contains different versions of a module type ({module_name}). "
                               f"Please use only one version for modules of the same type.")

    return dict(errors.items())


class Validation(ABC):
    """
    The base class for all custom field-level validations.
    """

    @abstractmethod
    def validate(self, field_name: str, value: Any):
        """
        Called by the __post_init__ of the module.

        :param field_name: The field name.
        :param value: The value of the field.

        :raises ValidationError: with error messages as list if the validation was not successful.
        """
        ...


class OneOf(Validation):
    """
    Checks if the value is one of the given possibilities.

    :param possibilities: The given possibilities as list.
    """

    def __init__(self, possibilities: list):
        self.possibilities = possibilities

    def validate(self, field_name: str, value: Any):
        """
        Called by the __post_init__ of the module.

        :param field_name: The field name.
        :param value: The value of the field.

        :raises ValidationError: with error messages as list if the validation was not successful.
        """
        if type(value) == list:
            for val in value:
                if val not in self.possibilities:
                    raise ValidationError([f"The value of the field '{field_name}' has to be "
                                           f"one of '{self.possibilities}' but was '{val}'."])
        else:
            if value not in self.possibilities:
                raise ValidationError([f"The value of the field '{field_name}' has to be "
                                       f"one of '{self.possibilities}' but was '{value}'."])


class Range(Validation):
    """
    Checks if the value is in between a min and max value (exclusive).

    :param min: The min value.
    :param max: The max value.
    :param exclusive: Exclusive or inclusive the given range.
    """

    def __init__(self, min: Optional[Union[int, float]] = None, max: Optional[Union[int, float]] = None,
                 exclusive: bool = True):
        self.min = min
        self.max = max
        self.exclusive = exclusive

    def validate(self, field_name: str, value: Union[int, float]):
        """
        Called by the __post_init__ of the module.

        :param field_name: The field name.
        :param value: The value of the field.

        :raises ValidationError: with error messages as list if the validation was not successful.
        """
        if self.exclusive:
            if self.min is not None and self.max is not None:
                if value <= self.min or value >= self.max:
                    raise ValidationError([f"The value of the field '{field_name}' has to be "
                                           f"in between '{self.min}' and '{self.max}' but was '{value}'."])
            elif self.min is not None:
                if value <= self.min:
                    raise ValidationError([f"The value of the field '{field_name}' has to be "
                                           f"in bigger than '{self.min}' but was '{value}'."])
            elif self.max is not None:
                if value >= self.max:
                    raise ValidationError([f"The value of the field '{field_name}' has to be "
                                           f"in smaller than '{self.max}' but was '{value}'."])
            else:
                # No min or max limits were given, we do nothing.
                pass
        else:
            if self.min is not None and self.max is not None:
                if value < self.min or value > self.max:
                    raise ValidationError([f"The value of the field '{field_name}' has to be "
                                           f"in between '{self.min}' and '{self.max}' (inclusive) but was '{value}'."])
            elif self.min is not None:
                if value < self.min:
                    raise ValidationError([f"The value of the field '{field_name}' has to be "
                                           f"bigger or equal than '{self.min}' but was '{value}'."])
            elif self.max is not None:
                if value > self.max:
                    raise ValidationError([f"The value of the field '{field_name}' has to be "
                                           f"smaller or equal than '{self.max}' but was '{value}'."])
            else:
                # No min or max limits were given, we do nothing.
                pass


class Regex(Validation):
    """
    Performs a regular expression validation with the given regular expression string.
    Succeeds if the given value matches regex.

    :param regex: The regular expression string to use.
    :param flags: The expression’s behaviour can be modified by specifying a flags value.
    :param error: Error message to raise in case of a validation error.
                  Can be interpolated with `{input}` and `{regex}`.
    """

    def __init__(self, regex: Union[str, bytes, Pattern], flags=0, error: Optional[str] = None):
        self.regex = (re.compile(regex, flags) if isinstance(regex, (str, bytes)) else regex)
        self.error = error or "{input} does not match expected pattern {regex}."

    def validate(self, field_name: str, value: Any):
        """
        Called by the __post_init__ of the module.

        :param field_name: The field name.
        :param value: The value of the field.

        :raises ValidationError: with error messages as list if the validation was not successful.
        """
        if self.regex.match(value) is None:
            raise ValidationError([self.error.format(input=value, regex=self.regex.pattern)])


class NestedListClassValidation(Validation):
    """
    Checks if the given configuration of a nested class (e.g. List[Threshold]) is correct.

    :param child_class: The nested class used for deserializing the received configuration.
    :param child_field_name: The field name of the nested configuration.
    """

    def __init__(self, child_class, child_field_name: str):
        self.child_class = child_class
        self.child_field_name = child_field_name

    def validate(self, field_name: str, value: Any):
        """
        Called by the __post_init__ of the module.

        :param field_name: The field name.
        :param value: The value of the field.

        :raises ValidationError: with error messages as list if the validation was not successful.
        """
        errors = []
        if field_name != self.child_field_name or type(value) != list:
            errors.append(f"The parameter '{self.child_field_name}' of type 'list' is missing. "
                          f"Got '{field_name}' of type '{type(field_name)}' instead.")
        for input_field in value:
            try:
                self.child_class(**input_field)
            except ValidationError as e:
                errors.extend(e.args[0])
        if errors:
            raise ValidationError(errors)
