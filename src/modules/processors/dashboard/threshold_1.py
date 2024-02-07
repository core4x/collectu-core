"""
The first key-value pair of the fields, whose value is a number (int or float) is taken.

The threshold object looks like the following:

| Required | Parameter | Description | Data Type | Default | Dynamic |
|:--------:|:----------| :-----------|:----------|:--------|:--------|
| x | limit | The limit value of the threshold. | Union[float, int] | None | |
| | message | The message of this threshold. | str | Threshold exceeded. | |
| | color | The color of this threshold. Has to be one of: light, info, warning, danger, success, primary, secondary, dark. | str | danger | |
"""
from dataclasses import dataclass, field
from typing import List, Any, Union, Dict

# Internal imports.
import data_layer
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import OneOf, validate_module, NestedListClassValidation, Range


@dataclass
class Threshold:
    """
    The configuration of a single threshold.
    """
    message: str = field(
        metadata=dict(description="The message of this threshold.",
                      required=False),
        default="Threshold exceeded.")
    color: str = field(
        metadata=dict(description="The color of this threshold. Has to be one of: "
                                  "light, info, warning, danger, success, primary, secondary, or dark.",
                      required=False,
                      validate=OneOf(possibilities=["light", "info", "warning", "danger", "success", "primary",
                                                    "secondary", "dark"])),
        default="danger")
    limit: Union[float, int] = field(
        metadata=dict(description="The limit value of the threshold.",
                      required=True),
        default=None)

    def __post_init__(self):
        validate_module(self)


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the tag module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module creates a colored (dependent from the threshold) textfield containing the value."
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
            default=4)
        thresholds: List[Threshold] = field(
            metadata=dict(description='The thresholds. Example: '
                                      '{"message": "Threshold exceeded.", "color": "danger", "limit": 50}',
                          required=False,
                          validate=NestedListClassValidation(child_class=Threshold, child_field_name="thresholds")),
            default_factory=list)

        def __post_init__(self):
            super().__post_init__()
            thresholds = []
            for threshold_dict in self.thresholds:
                thresholds.append(Threshold(**threshold_dict))
            setattr(self, "thresholds", thresholds)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.latest_data = {}
        """Holds the latest data, which is requested by the frontend view."""
        data_layer.dashboard_modules.append(self)
        """Self register in data layer. This list is used by the frontend view to request the latest data."""

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.

        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {"color": ["light", "info", "warning", "danger", "success", "primary", "secondary", "dark"]}

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
                            "thresholds": [x.__dict__ for x in self.configuration.thresholds],
                            "type": "threshold",
                            "data": data.__dict__}

        return data
