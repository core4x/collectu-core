"""
The last time is used.
"""
from dataclasses import dataclass, field
from copy import deepcopy

# Internal imports.
import models
from modules.processors.base.base import AbstractProcessorModule
from models.validations import Range


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module merges a defined number of data objects into one."
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
        number_of_objects_to_merge: int = field(
            metadata=dict(description="The number of data objects to be merged. "
                                      "When the number is reached, the complete data object is forwarded.",
                          required=False,
                          dynamic=True,
                          validate=Range(min=1)),
            default=2)
        overwrite_existing_keys: bool = field(
            metadata=dict(description="If a key is already gathered, a list is created if this is false. "
                                      "Otherwise, the field key is overwritten by the last received value.",
                          required=False),
            default=False)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.buffered_data: models.Data = models.Data(measurement="")
        """The merged data objects."""
        self.counter = 0
        """The number of already merged data objects."""

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        if not self.buffered_data.fields:
            # This should be our first entry.
            self.buffered_data = data
            self.counter = 1
        else:
            self.counter += 1
            # Take the last time.
            self.buffered_data.time = data.time

            # Add the fields
            for key, value in data.fields.items():
                if not isinstance(value, list) and key in self.buffered_data.fields.keys() and \
                        not self.configuration.overwrite_existing_keys:
                    # If the value is not already a list, we make it one.
                    value = [value]
                if key not in self.buffered_data.fields.keys() or self.configuration.overwrite_existing_keys:
                    self.buffered_data.fields[key] = value
                else:
                    self.buffered_data.fields[key] = self.buffered_data.fields[key] + value if isinstance(
                        self.buffered_data.fields[key], list) else [self.buffered_data.fields[key]] + value

            # Add the tags.
            for key, value in data.tags.items():
                if not isinstance(value, list) and key in self.buffered_data.tags.keys() and \
                        not self.configuration.overwrite_existing_keys:
                    # If the value is not already a list, we make it one.
                    value = [value]
                if key not in self.buffered_data.tags.keys() or self.configuration.overwrite_existing_keys:
                    self.buffered_data.tags[key] = value
                else:
                    self.buffered_data.tags[key] = self.buffered_data.tags[key] + value if isinstance(
                        self.buffered_data.tags[key], list) else [self.buffered_data.tags[key]] + value

        if self.counter >= self._dyn(self.configuration.number_of_objects_to_merge, data_type="int"):
            # Set the measurement name.
            self.buffered_data.measurement = self._dyn(self.configuration.measurement)
            data = deepcopy(self.buffered_data)
            # Reset the data object.
            self.buffered_data = models.Data(measurement="")
            # Reset the counter.
            self.counter = 0
            return data
        else:
            # We return an empty (no fields) data object. This object will not be forwarded.
            return models.Data(measurement="")
