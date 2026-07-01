"""
This is the base class of all input modules. All implemented input modules have to be derived from this class.
The derived child class has to be named 'InputModule', 'TagModule', or 'VariableModule'.
"""
import time
import inspect
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

# Internal imports.
import config
import models
from modules.base.base import AbstractModule
from metrics import metrics_registry, data_context_map


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
        self._metrics = metrics_registry.register(
            module_id=configuration.id,
            module_name=configuration.module_name,
        )


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
        self._metrics = metrics_registry.register(
            module_id=configuration.id,
            module_name=configuration.module_name,
        )


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
        self._metrics = metrics_registry.register(
            module_id=configuration.id,
            module_name=configuration.module_name,
        )

    def run(self, data: models.Data):
        """
        External entry point for passing data into the module.

        Sets the current input data for dynamic variable resolution, invokes _run to retrieve the generated
        key-value pairs, and merges them into the data object's fields and/or tags depending on the module configuration.
        If replace_existing is set, the corresponding fields or tags dict is cleared before merging.
        The updated data object is then forwarded to all downstream links.

        :param data: The data object to enrich with the tag module's output.
        """
        try:
            if not self.active:
                return

            ctx = data_context_map.get(data)
            if ctx is not None:
                self._metrics.record_link_wait(time.monotonic() - ctx.link_ts)
            self._metrics.record_received()

            # Set the current data object.
            self.current_input_data = data

            # Execute the module specific logic.
            t0 = time.monotonic()
            if not inspect.iscoroutinefunction(self._run):
                key_values = self._run() or {}
            else:
                key_values = AbstractModule._invoke_async(method=self._run) or {}
            self._metrics.record_processing_time(time.monotonic() - t0)
            self._metrics.record_processed()

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
            self._metrics.record_error()
            self.logger.error("Something went wrong while executing tag module {0} ({1}): {2}"
                              .format(self.configuration.module_name, self.configuration.id, str(e)),
                              exc_info=config.EXC_INFO)

    @abstractmethod
    def _run(self) -> dict[str, Any]:
        """
        Internal method for executing the module logic. Must be implemented by every derived TagModule class.

        May be declared as either a regular or an async method — both are supported:

            # Synchronous:
            def _run(self) -> dict[str, Any]:
                return {"location": "Berlin"}

            # Asynchronous:
            async def _run(self) -> dict[str, Any]:
                result = await fetch_tag_value()
                return {"location": result}

        The current input data is accessible via self.current_input_data for resolving dynamic variables.
        The returned dict is merged into the data object's fields and/or tags by the calling run() method —
        _run itself should not modify the data object directly.

        :returns: A dict containing the generated key-value pairs.
        """
        return {}
