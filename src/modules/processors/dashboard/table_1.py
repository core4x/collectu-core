"""
The fields and tags are shown in json format.
"""
from dataclasses import dataclass, field

# Internal imports.
import data_layer
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import Range


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the tag module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module creates a table on the dashboard."
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
        dashboard: str = field(
            metadata=dict(description="The dashboard this visualization belongs to.",
                          required=False),
            default="Default")
        show_event: bool = field(
            metadata=dict(description="If enabled, the dashboard is highlighted if new data is shown.",
                          required=False),
            default=True)
        width: int = field(
            metadata=dict(description="The width of the dashboard. Has to be between 1 and 12.",
                          required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=12)
        points: int = field(
            metadata=dict(description="The number of points to be displayed. Can be between 1 and 100000.",
                          required=False,
                          validate=Range(min=0, max=100000)),
            default=10)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.latest_data = {}
        """Holds the latest data, which is requested by the frontend view."""
        data_layer.dashboard_modules.append(self)
        """Self register in data layer. This list is used by the frontend view to request the latest data."""

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        self.latest_data = {"id": self.configuration.id,
                            "dashboard": self.configuration.dashboard,
                            "show_event": self.configuration.show_event,
                            "name": self.configuration.name,
                            "width": self.configuration.width,
                            "description": self.configuration.description,
                            "type": "table",
                            "points": self.configuration.points,
                            "data": data.__dict__}

        return data
