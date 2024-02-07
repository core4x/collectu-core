"""
The time delta value is appended as field ('time_delta') of data type int to the second given data object.
Please notice: If the time delta is smaller than a minute, but the unit is min, you receive 0.
"""
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from copy import deepcopy

# Internal imports.
import models
from modules.processors.base.base import AbstractProcessorModule
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
    description: str = "This module calculates the time delta between two given data objects."
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
        unit_of_time: str = field(
            metadata=dict(description="The unit of the calculated time delta. Can be 'min', 's', 'ms', or 'µs'.",
                          required=False,
                          validate=OneOf(["min", "s", "ms", "µs"])),
            default="s")

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.previous_data: Optional[models.Data] = None
        """The previous data objects."""

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.

        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {"unit_of_time": ["min", "s", "ms", "µs"]}

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        time_delta = None
        if self.previous_data:
            delta = data.time - self.previous_data.time
            time_delta = delta.total_seconds()
            if self.configuration.unit_of_time == "min":
                time_delta = int(round(time_delta / 60))
            elif self.configuration.unit_of_time == "s":
                time_delta = int(round(time_delta))
            elif self.configuration.unit_of_time == "ms":
                time_delta = int(round(time_delta * 1000))
            elif self.configuration.unit_of_time == "µs":
                time_delta = int(round(time_delta * 1000 * 1000))

        self.previous_data = deepcopy(data)
        if time_delta is not None:
            data.fields["time_delta"] = time_delta
        return data
