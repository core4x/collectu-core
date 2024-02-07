"""
If the key does not exist, the already merged data object is forwarded and the new received data object is dismissed.

TODO: This is not tested.
"""
import datetime
from dataclasses import dataclass, field
from copy import deepcopy

# Internal imports.
import models
from modules.processors.base.base import AbstractProcessorModule


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module merges data objects until a defined field value changes."
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
        measurement: str = field(
            metadata=dict(description="The measurement name of the forwarded data object.",
                          required=False,
                          dynamic=True),
            default="Merged data")
        field_key: str = field(
            metadata=dict(description="The field key which shall be checked for changes.",
                          required=True,
                          dynamic=True),
            default=None)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.buffered_data: models.Data = models.Data(measurement="")
        """The merged data objects."""
        self.previous_key_value = None
        """The previous key value which is checked for changes."""

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        # Check if key exists.
        try:
            current_value = data.fields.get(self._dyn(self.configuration.field_key))
        except KeyError as e:
            # The key does not exist, so we forward the already merged data object.
            # Set the measurement name.
            self.buffered_data.measurement = self._dyn(self.configuration.measurement)
            merged_data = deepcopy(self.buffered_data)
            # Reset the merged data object and dismiss the current one.
            self.buffered_data = models.Data(measurement="")
            self.previous_key_value = None
            return merged_data

        # If we are here, the key exists.
        # First we have to check if the value has changed or this is the first data object.
        if self.previous_key_value is None or current_value == self.previous_key_value:
            # Store the last received value.
            self.previous_key_value = current_value
            # Start merging.
            if not self.buffered_data.fields:
                # This should be our first entry.
                self.buffered_data = data
            else:
                # Take the last time.
                self.buffered_data.time = data.time

                # Add the fields
                for key, value in data.fields.items():
                    if not isinstance(value, list) and key in self.buffered_data.fields.keys():
                        # If the value is not already a list, we make it one.
                        value = [value]
                    if key not in self.buffered_data.fields.keys():
                        self.buffered_data.fields[key] = value
                    else:
                        self.buffered_data.fields[key] = self.buffered_data.fields[key] + value if isinstance(
                            self.buffered_data.fields[key], list) else [self.buffered_data.fields[key]] + value

                # Add the tags.
                for key, value in data.tags.items():
                    if not isinstance(value, list) and key in self.buffered_data.tags.keys():
                        # If the value is not already a list, we make it one.
                        value = [value]
                    if key not in self.buffered_data.tags.keys():
                        self.buffered_data.tags[key] = value
                    else:
                        self.buffered_data.tags[key] = self.buffered_data.tags[key] + value if isinstance(
                            self.buffered_data.tags[key], list) else [self.buffered_data.tags[key]] + value

                # We return an empty (no fields) data object. This object will not be forwarded.
                return models.Data(measurement="")
        else:
            # The value has changed. Forward the already merged data and store the new one.
            # Set the measurement name.
            self.buffered_data.measurement = self._dyn(self.configuration.measurement)
            self.buffered_data.time = datetime.datetime.utcnow()
            merged_data = deepcopy(self.buffered_data)
            # Reset the merged data to the newly received object.
            self.buffered_data = data
            self.previous_key_value = current_value
            return merged_data
