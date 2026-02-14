"""
This is the base class of all input modules. All implemented input modules have to be derived from this class.
The derived child class has to be named 'InputModule', 'TagModule', or 'VariableModule'.
"""
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

# Internal imports.
import config
import data_layer
import models
from modules.base.base import AbstractModule


class AbstractInputModule(AbstractModule):
    """
    !!!The derived child class has to be named 'InputModule'!!!

    Abstract base class for the input module.
    This class shows the required methods to be implemented by the derived child.

    Use: super().__init__(configuration)

    to call this base initialization when implementing the InputModule __init__.

    :param configuration: The configuration object of the input module.
    """

    @dataclass
    class Configuration(models.InputModule):
        """
        The configuration model of the module.
        """
        pass

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)


class AbstractVariableModule(AbstractModule):
    """
    !!!The derived child class has to be named 'VariableModule'!!!

    Abstract base class for the variable module.
    This class shows the required methods to be implemented by the derived child.

    Use: super().__init__(configuration, input_module_instance)

    to call this base initialization when implementing the VariableModule __init__.

    :param configuration: The configuration object of the variable module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        pass

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration)
        self.input_module_instance = input_module_instance
        """The input module instance."""


class AbstractTagModule(AbstractModule):
    """
    !!!The derived child class has to be named 'TagModule'!!!

    Abstract base class for the tag module.
    This class shows the required methods to be implemented by the derived child.

    Use: super().__init__(configuration, input_module_instance)

    to call this base initialization when implementing the TagModule __init__.

    :param configuration: The configuration object of the tag module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """

    @dataclass
    class Configuration(models.TagModule):
        """
        The configuration model of the module.
        """
        pass

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration)
        self.input_module_instance = input_module_instance
        """The input module instance."""
        self.current_input_data: Optional[models.Data] = None
        """The currently received data object. Used for replacing dynamic variables with local data."""

    def run(self, data: models.Data):
        """
        Method for executing the module.

        :param data: The data object.
        """
        try:
            if self.active:
                # Set the current data object.
                self.current_input_data = data
                # Execute the module specific logic.
                key_values = self._run() or {}
                if self.configuration.is_field:
                    if self.configuration.replace_existing:
                        data.fields = {}
                if self.configuration.is_tag:
                    if self.configuration.replace_existing:
                        data.tags = {}
                for key, value in key_values.items():
                    if self.configuration.is_field:
                        data.fields[key] = value
                    if self.configuration.is_tag:
                        data.tags[key] = value

                # Call the subsequent links.
                self._call_links(data)
                # Reset the current data object.
                self.current_input_data = None
        except Exception as e:
            self.logger.error("Something went wrong while executing tag module {0} ({1}): {2}"
                              .format(self.configuration.module_name, self.configuration.id, str(e)),
                              exc_info=config.EXC_INFO)

    @abstractmethod
    def _run(self) -> dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        return {}
