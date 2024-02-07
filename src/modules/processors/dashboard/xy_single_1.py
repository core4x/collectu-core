"""
The both defined lists (x_keys and y_keys) need the same length.
The given values have to be of type int or float.

Only values (of the defined keys), which are of type int or float are used.
"""
from dataclasses import dataclass, field
from typing import List

# Internal imports.
import data_layer
from models.validations import validate_module, ValidationError, Range
from modules.processors.base.base import AbstractProcessorModule, models


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the tag module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module creates a x/y plot on the dashboard using single values."
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
        title: str = field(
            metadata=dict(description="The title of the dashboard.",
                          required=False),
            default="")
        width: int = field(
            metadata=dict(description="The width of the dashboard. Has to be between 1 and 12.",
                          required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=8)
        x_keys: List[str] = field(
            metadata=dict(description="The field or tag key for the x values.",
                          required=False),
            default_factory=list)
        y_keys: List[str] = field(
            metadata=dict(description="The field or tag key for the y values.",
                          required=False),
            default_factory=list)
        show_lines: bool = field(
            metadata=dict(description="If enabled, lines are drawn between the markers.",
                          required=False),
            default=True)
        points: int = field(
            metadata=dict(description="The number of points to be displayed. Can be between 0 and 100000. "
                                      "If you want to use a time difference, set this parameter to 0 (default).",
                          required=False,
                          validate=Range(min=-1, max=100000)),
            default=0)
        time_range: int = field(
            metadata=dict(description="The time range in minutes you want to display.",
                          required=False,
                          validate=Range(min=0, max=1440)),
            default=5)
        x_axis_name: str = field(
            metadata=dict(description="The name of the x axis.",
                          required=False),
            default="")
        y_axis_name: str = field(
            metadata=dict(description="The name of the y axis.",
                          required=False),
            default="")

        def __post_init__(self):
            # Make custom validation in order to check that both lists are the same length.
            if len(self.x_keys) != len(self.y_keys):
                raise ValidationError(["The lists of x_keys and y_keys need the same length."])
            validate_module(self)

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
                            "type": "xy_single",
                            "x_keys": self.configuration.x_keys,
                            "y_keys": self.configuration.y_keys,
                            "x_axis_name": self.configuration.x_axis_name,
                            "y_axis_name": self.configuration.y_axis_name,
                            "show_lines": self.configuration.show_lines,
                            "points": self.configuration.points,
                            "time_range": self.configuration.time_range,
                            "data": data.__dict__,
                            "title": self.configuration.title}

        return data
