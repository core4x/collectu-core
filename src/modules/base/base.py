"""
This is the base class for all modules.
"""
__version__: int = 1
"""The auto-generated version of the module."""
from abc import ABC
import logging
import os
from threading import Thread
from typing import Any, Optional, Union
import copy
import ast

# Internal imports.
import config
import data_layer
import models
import utils.plugin_interface


class DynamicVariableException(Exception):
    """
    Base class for dynamic variable errors.
    The exception contains an error message.
    """
    pass


class AbstractModule(ABC):
    """
    All modules have to be derived from this one.

    :param configuration: The configuration object of the module.
    """
    version: int = __version__
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = ""
    """A short description."""
    author: str = ""
    """The author name."""
    email: str = ""
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""

    def __init__(self, configuration):
        self.logger: logging.Logger = logging.getLogger(
            f"{config.APP_NAME.lower()}.{configuration.module_name}.{configuration.id}")
        """The logger of the instantiated child class."""
        self.configuration = configuration
        """The configuration of the module."""
        try:
            self.import_third_party_requirements()
            """Import the required third party packages."""
        except ImportError as e:
            if bool(int(os.environ.get('AUTO_INSTALL', '0'))):
                self.logger.warning("Third party requirements are not fulfilled: {0} "
                                    "Trying to auto install required third party packages: '{1}'."
                                    .format(str(e), ', '.join(map(str, self.third_party_requirements))))
                for package in self.third_party_requirements:
                    utils.plugin_interface.install_plugin_requirement(package)
                self.import_third_party_requirements()
            else:
                self.logger.critical("Could not import required packages: {0}. Please try to install '{1}'."
                                     .format(str(e), ', '.join(map(str, self.third_party_requirements))))
                raise ImportError
        self.active: bool = self.configuration.active
        """Is the module currently active. 
        Not the same as self.configuration.active, which represents the general state!"""

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        Import here the third party requirements as follows:
          global package
          import package

        :returns: True if the import was successful.
        """
        try:
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    @staticmethod
    def get_config_data(input_module_instance=None) -> dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {}

    def start(self):
        """
        Method for starting the module. Is called by a separate thread.
        InputModules and OutputModules normally connect to a data source. VariableModules start a subscription.
        The start method is only called if the module is active (self.configuration.active).
        """
        ...

    def stop(self):
        """
        Method for stopping the module. Is called by a separate thread.
        TagModules and ProcessorModules do (normally) not need to implement a stop routine.
        """
        ...

    def _call_links(self, data: models.Data):
        """
        Calls all links of the module.
        The linked module is only called if self.active is true.

        :param data: The data object.
        """
        if data.measurement.strip():
            # During the stopping procedure, it could happen, that the entry does no longer exist.
            # We catch it here.
            if self.configuration.id not in data_layer.module_data:
                self.logger.error("Could not find module '{0}' in data layer."
                                  .format(str(self.configuration.id)))
            else:
                # Store the data in the latest data entry.
                data_layer.module_data[self.configuration.id].latest_data = data
            for module_id in getattr(self.configuration, "links", []):
                try:
                    if data_layer.module_data[module_id].instance.active:
                        Thread(target=data_layer.module_data[module_id].instance.run,
                               # Make a deepcopy before sending to the next module.
                               # Otherwise, the original object is manipulated by the module.
                               args=(copy.deepcopy(data),),
                               daemon=False,
                               name="Link_{0}_to_{1}".format(self.configuration.id, module_id)).start()
                except KeyError as e:
                    self.logger.error("Could not find linked module '{0}' in the module data.".format(module_id))
                except Exception as e:
                    self.logger.error("Could not execute linked module '{0}': {1}".format(module_id, str(e)),
                                      exc_info=config.EXC_INFO)

    def _dyn(self, input_data: Any, data_type: Optional[Union[list[str], str]] = None) -> Any:
        """
        This method receives an input value and replaces all dynamic variables e.g. '${module_id.key}'
        with the current value of the linked module.
        All attributes of a variable possibly containing variables have to be given to this function before applied.

        !CAUTION: we can not guarantee that the data type fits the one defined for the field!
        However, you can try to convert to one of the given data types.
        If a conversion is not possible, we will raise a DynamicVariableException.
        But if more than one dynamic variable was in the input_string, we also return a string.

        If the replacement of the dynamic variable went wrong (e.g. because of a missing value or wrong data type),
        an DynamicVariableException is raised.

        :param input_data: The input data possibly containing dynamic variables.
        :param data_type: The data type we try the dynamic variable. Can be list, dict, str, int, float, or bool.

        :returns: The input with the dynamic variables replaced by the actual value.
        """
        try:
            available_data_types = {"str": str, "bool": bool, "float": float, "int": int, "list": list, "dict": dict}
            """A dictionary containing all available data types for conversion."""

            # To be safe, we make the input_string a string.
            input_string = str(input_data)

            # Convert to list.
            if data_type is None:
                data_type = []
            if not isinstance(data_type, list):
                data_type = [data_type]
            # Make every entry a lowered string.
            converted_data_types = [str(item).lower() for item in data_type]
            # Check if it is an allowed data type.
            for index, item in enumerate(data_type):
                if item not in available_data_types.keys():
                    raise DynamicVariableException(f"Unknown data type {item}. "
                                                   f"Allowed types are: {', '.join(available_data_types.keys())}.")
                else:
                    # Replace the string with a python data type.
                    converted_data_types[index] = available_data_types[item]

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
                    raise DynamicVariableException("Found an incomplete marker in '{0}'.".format(input_string))
                else:
                    # If there are no more markers, we leave this function.
                    return

                extracted_variables.append(result)
                new_input_string = input_string_temp.replace("${" + result + "}", '')
                # Recursively call this function until there are no more dynamic variables.
                _extract_variables(new_input_string)

            # Make input to string to be safe and extract dynamic variables if there are.
            _extract_variables(str(input_string))

            processed_input_string = input_string
            if extracted_variables:
                for variable_text in extracted_variables:
                    module_id = variable_text.split('.', 1)[0]
                    key = variable_text.split('.', 1)[1]
                    if module_id == "local":
                        if getattr(self, "current_input_data", None) is not None:
                            data = self.current_input_data
                            # Check if the key is 'measurement'.
                            if key.lower() == "measurement":
                                value = data.measurement
                            elif key.lower() == "time":
                                value = data.time
                            else:
                                # Check if the key is in the fields dict.
                                value = data.fields.get(key, None)
                                if value is None:
                                    # If it was not in the fields dict, we check if the key is in the tags dict.
                                    value = data.tags.get(key, None)
                                if value is None:
                                    raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                                   "Could not find key '{1}' in fields or tags."
                                                                   .format(input_string, key))
                        else:
                            raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                           "Referenced module has no latest data. "
                                                           "Only tag, output, and processor modules support 'local'."
                                                           .format(input_string))
                    elif module_id == "env":
                        value = os.getenv(key, None)
                        if value is None:
                            raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                           "Could not find key '{1}' in environment variables."
                                                           .format(input_string, key))
                    else:
                        module_entry = data_layer.module_data.get(module_id, None)
                        if module_entry is not None:
                            if module_entry.latest_data is not None:
                                data = module_entry.latest_data
                                # Check if the key is in the fields dict.
                                value = data.fields.get(key, None)
                                if value is None:
                                    # If it was not in the fields dict, we check if the key is in the tags dict.
                                    value = data.tags.get(key, None)
                                if value is None:
                                    raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                                   "Could not find key '{1}' in fields or tags."
                                                                   .format(input_string, key))
                            else:
                                raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                               "Referenced module has no latest data."
                                                               .format(input_string))
                        else:
                            raise DynamicVariableException("Could not replace dynamic variable '{0}'. "
                                                           "Could not find module with the id '{1}'."
                                                           .format(input_string, module_id))

                    # Replace the input with the value.
                    if len(extracted_variables) == 1 and input_string.startswith(
                            "${") and input_string.endswith("}"):
                        # If it was only one dynamic variable, we keep the data type of the input.
                        processed_input_string = value
                    else:
                        # We have to convert it to a string.
                        processed_input_string = processed_input_string.replace(
                            "${" + variable_text + "}", str(value))

            try:
                # This make strings to lists and dicts, if they are.
                processed_input_string = ast.literal_eval(processed_input_string)
            except Exception as e:
                pass

            # Try to convert to the given data type.
            successfully_converted: bool = False
            for defined_data_type in converted_data_types:
                try:
                    if defined_data_type == list:
                        if not isinstance(processed_input_string, list):
                            processed_input_string = [processed_input_string]
                    else:
                        processed_input_string = defined_data_type(processed_input_string)
                    successfully_converted = True
                    break
                except Exception as e:
                    continue
            if not successfully_converted and converted_data_types:
                raise DynamicVariableException(f"Could not convert dynamic variable '{processed_input_string}' "
                                               f"to one of the given data types: {', '.join(data_type)}.")
            return processed_input_string
        except DynamicVariableException as e:
            raise DynamicVariableException(str(e))
        except Exception as e:
            raise DynamicVariableException("Something unexpected went wrong while trying to "
                                           "replace dynamic variable '{0}': {1}"
                                           .format(input_string, str(e)))
