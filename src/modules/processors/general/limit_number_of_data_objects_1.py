""""""
import time
from dataclasses import dataclass, field

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
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
    description: str = "This module only forwards a defined number of data objects."
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
        number_of_data_objects: int = field(
            metadata=dict(description="The number of data objects to be forwarded.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=0, max=1000)),
            default=1)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.counter = 0
        """The number of already forwarded data objects."""

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        if self.counter < self.configuration.number_of_data_objects:
            self.counter += 1
            return data
        else:
            # Create an empty data object, which will not be forwarded.
            return models.Data(measurement="", fields={})
