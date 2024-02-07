""""""
from dataclasses import dataclass, field
from typing import List

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
    public: bool = False
    """Is this module public?"""
    description: str = "This module transforms values from one coordinate system to another."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["opencv-contrib-python==4.6.0.66"]
    """Define your requirements here."""
    # These requirements are custom validated below.
    field_requirements: list[str] = []
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        x_ratio_pixel_in_mm: float = field(
            metadata=dict(description="How many mm is one pixel in x direction.",
                          required=True,
                          validate=Range(exclusive=True, min=0)),
            default=None)
        y_ratio_pixel_in_mm: float = field(
            metadata=dict(description="How many mm is one pixel in y direction.",
                          required=True,
                          validate=Range(exclusive=True, min=0)),
            default=None)
        center_marker_x_in_pixel: float = field(
            metadata=dict(description="The x position of the marker center in pixel.",
                          required=True),
            default=None)
        center_marker_y_in_pixel: float = field(
            metadata=dict(description="The y position of the marker center in pixel.",
                          required=True),
            default=None)
        center_marker_x_in_mm: float = field(
            metadata=dict(description="The x position of the marker center in mm.",
                          required=True),
            default=None)
        center_marker_y_in_mm: float = field(
            metadata=dict(description="The y position of the marker center in mm.",
                          required=True),
            default=None)
        x_keys: List[str] = field(
            metadata=dict(description="The keys, their values are in x direction and "
                                      "shall be calculated in world coordinates.",
                          required=False),
            default_factory=list)
        y_keys: List[str] = field(
            metadata=dict(description="The keys, their values are in y direction and "
                                      "shall be calculated in world coordinates.",
                          required=False),
            default_factory=list)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        :returns: True if the import was successful.
        """
        try:
            # Import third party packages here and mark them as global.
            global np
            import numpy as np
            global cv2
            import cv2
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        for key, value in data.fields.items():
            if key in self.configuration.x_keys or not self.configuration.x_keys:
                if isinstance(value, float) or isinstance(value, int):
                    data.fields[key] = self.configuration.center_marker_x_in_mm - (
                            value - self.configuration.center_marker_x_in_pixel) * self.configuration.x_ratio_pixel_in_mm
            if key in self.configuration.y_keys or not self.configuration.y_keys:
                if isinstance(value, float) or isinstance(value, int):
                    # The - ratio is caused by the opposite positive coordinate axes.
                    data.fields[key] = self.configuration.center_marker_y_in_mm - (
                            value - self.configuration.center_marker_y_in_pixel) * -self.configuration.y_ratio_pixel_in_mm
        return data
