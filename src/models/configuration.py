"""
The models are used for the deserialization of the configuration file.
"""
from dataclasses import dataclass, field, fields
import string
import os
import random

# Internal imports.
import models.validations


@dataclass
class Module:
    """
    The base module class.

    Every not required field has to provide a default value.
    """
    id: str = field(
        metadata=dict(description="The unique id of the module.",
                      required=False),
        default=''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(19)))
    module_name: str = field(
        metadata=dict(description="The name of the module.",
                      required=True),
        default=None)
    version: int = field(
        metadata=dict(description="The version of the module.",
                      required=False),
        default=0)
    active: bool = field(
        metadata=dict(description="Is this module active.",
                      required=False),
        default=True)
    name: str = field(
        metadata=dict(description="The user-specific name of the module.",
                      required=False),
        default="")
    description: str = field(
        metadata=dict(description="The description of the module.",
                      required=False),
        default="")
    panel: str = field(
        metadata=dict(description="The panel where the module is placed.",
                      required=False,
                      validate=models.validations.OneOf(["panel-1", "panel-2", "panel-3", "panel-4", "panel-5"])),
        default="panel-1")
    x: int = field(
        metadata=dict(description="The x position of the module on the canvas.",
                      required=False),
        default=0)
    y: int = field(
        metadata=dict(description="The y position of the module on the canvas.",
                      required=False),
        default=0)

    def __post_init__(self):
        models.validations.validate_module(self)

    def __getattribute__(self, name):
        """
        Replace all environment variables if attribute is accessed for non-dynamic attributes.
        """
        input_value = super().__getattribute__(name)
        # Get the field metadata.
        try:
            dataclass_fields = super().__getattribute__('__dataclass_fields__')
            field_meta = dataclass_fields.get(name).metadata if name in dataclass_fields else {}
        except AttributeError:
            field_meta = {}

        if field_meta.get("dynamic", False):
            # Do not check dynamic variables. This should be done in the modules themselves.
            return input_value

        # Get the data type.
        annotations = super().__getattribute__('__annotations__')
        data_type = annotations.get(name, None)

        # Replace dynamic environment variables.
        try:
            extracted_variables: list[str] = []
            """The extracted dynamic variables as str, without the markers (e.g. 'REST_Test.[0]')."""

            def _extract_variables(input_string_temp: str):
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
                elif start != -1 and end == -1:
                    # Found an incomplete marker.
                    return
                else:
                    # If there are no more markers, we leave this function.
                    return

                extracted_variables.append(result)
                new_input_string = input_string_temp.replace("${" + result + "}", '')
                # Recursively call this function until there are no more dynamic variables.
                _extract_variables(new_input_string)

            # Make input to string to be safe and extract dynamic variables if there are.
            _extract_variables(str(input_value))

            processed_input_string = input_value
            if extracted_variables:
                for variable_text in extracted_variables:
                    marker_type = variable_text.split('.', 1)[0]
                    key = variable_text.split('.', 1)[1]

                    if marker_type == "env":
                        value = os.getenv(key, None)
                        if value is not None:
                            # Replace the input with the value.
                            processed_input_string = processed_input_string.replace("${" + variable_text + "}",
                                                                                    str(value))

            input_value = processed_input_string
            # Try to convert to the given data type.
            if data_type in [str, int, float, bool, list]:
                try:
                    input_value = data_type(processed_input_string)
                except Exception as e:
                    pass

        except Exception as e:
            pass
        finally:
            return input_value


@dataclass
class ProcessorModule(Module):
    """
    The abstract ProcessorModule class.
    """
    links: list[str] = field(
        metadata=dict(description="The links of this module.",
                      required=False),
        default_factory=list)


@dataclass
class TagModule(Module):
    """
    The abstract TagModule class.
    """
    is_tag: bool = field(
        metadata=dict(description="Boolean indicating if the data is to be stored as a tags.",
                      required=False),
        default=False)
    is_field: bool = field(
        metadata=dict(description="Boolean indicating if the data is to be stored as fields.",
                      required=False),
        default=True)
    links: list[str] = field(
        metadata=dict(description="The links of this module.",
                      required=False),
        default_factory=list)


@dataclass
class VariableModule(Module):
    """
    The abstract VariableModule class.
    """
    links: list[str] = field(
        metadata=dict(description="The links of this module.",
                      required=False),
        default_factory=list)
    measurement: str = field(
        metadata=dict(description="The measurement name.",
                      required=False),
        default="test")
    start_priority: int = field(
        metadata=dict(description="The start (and stop) priority. "
                                  "A module with greater priority is started before (and stopped after) "
                                  "a module with a lower priority. "
                                  "If the start priority is 0, the regular starting order is used.",
                      required=False,
                      validate=models.validations.Range(min=0, exclusive=False)),
        default=0)


@dataclass
class InputModule(Module):
    """
    The abstract InputModule class.
    """
    pass


@dataclass
class OutputModule(Module):
    """
    The abstract OutputModule class.
    """
    buffered: bool = field(
        metadata=dict(description="If true, data is buffered, when the output module is not accessible. "
                                  "An output module with is_buffer is `True` has to be configured.",
                      required=False),
        default=False)
    is_buffer: bool = field(
        metadata=dict(description="Is this output module a buffer. "
                                  "Module attribute can_be_buffer has to be `True`. "
                                  "Exactly one buffer can be configured.",
                      required=False),
        default=False)
