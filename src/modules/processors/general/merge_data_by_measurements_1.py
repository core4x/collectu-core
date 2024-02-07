"""
If a measurement already exists, it is overwritten.
If a field or tag key already exists, the last received one is taken.
"""
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Dict, Any

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
    description: str = "This module merges a defined number of data objects with unique measurement names."
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
        number_of_unique_measurements_to_merge: int = field(
            metadata=dict(description="The number of unique measurement names to be merged. "
                                      "When the number is reached, the complete data object is forwarded.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=1)),
            default=2)
        add_merged_measurement_names_as_tag: bool = field(
            metadata=dict(description="Do you want to add the merged measurement names as a list to the tags. "
                                      "The key will be `merged_measurement_names`.",
                          required=False,
                          dynamic=False),
            default=False)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.measurements: Dict[str, Any] = {}
        """The already merged gathered data objects with the measurement name as key."""

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        self.measurements[data.measurement] = {"fields": data.fields, "tags": data.tags}

        if len(self.measurements.keys()) >= self.configuration.number_of_unique_measurements_to_merge:
            # Merge all gathered dictionaries.
            fields = {key: value for dictionary in
                      [dictionary.get("fields") for dictionary in self.measurements.values()]
                      for key, value in dictionary.items()}
            tags = {key: value for dictionary in
                    [dictionary.get("tags") for dictionary in self.measurements.values()]
                    for key, value in dictionary.items()}
            if self.configuration.add_merged_measurement_names_as_tag:
                tags["merged_measurement_names"] = list(self.measurements.keys())

            merged_data = models.Data(measurement=self._dyn(self.configuration.measurement),
                                      fields=deepcopy(fields),
                                      tags=deepcopy(tags))
            # Reset the buffer.
            self.measurements = {}
            return merged_data
        else:
            # We return an empty (no fields) data object. This object will not be forwarded.
            return models.Data(measurement="")
