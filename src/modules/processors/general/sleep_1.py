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
    description: str = "This module waits a defined interval until it forwards the given data."
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
        sleep_time: float = field(
            metadata=dict(description="The interval in seconds until the data is forwarded. "
                                      "Has to be between (exclusive) 0 and 86400 s (24 h).",
                          required=False,
                          dynamic=False,
                          validate=Range(min=0, max=86400)),
            default=1)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        time.sleep(self.configuration.sleep_time)
        return data
