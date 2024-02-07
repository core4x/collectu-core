"""
This module calculates the offset between an aruco marker and a given point.

The point (in pixel coordinates) as to be contained in the data object with the following field keys:

- `point_x`: As int/float.
- `point_y`: As int/float.

In addition, we need a detected aruco marker as fields.
This can be done with the processor module `detect_aruco_marker_1`.

This module creates the following fields:

- `distance_x`: The x distance between the center of the aruco marker and the point in mm.
- `distance_y`: The y distance between the center of the aruco marker and the point in mm.
- `scalefactor`: The factor between the actual and the set aruco edge length.
"""
from dataclasses import dataclass, field
import math

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module calculates the offset between an aruco marker and a given point."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    field_requirements: list[str] = ["((key point_x with int/float) "
                                     "and (key point_y with int/float) "
                                     "and (key bottom_left_x with int/float) "
                                     "and (key bottom_left_y with int/float) "
                                     "and (key bottom_right_x with int/float) "
                                     "and (key bottom_right_y with int/float) "
                                     "and (key center_x with int/float) "
                                     "and (key center_y with int/float))"]
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        aruco_edge_length: float = field(
            metadata=dict(description="The length of the aruco marker edge in mm.",
                          required=True),
            default=50.0)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        center_x = data.fields.get("center_x")
        center_y = data.fields.get("center_y")

        x1 = data.fields.get("bottom_left_x")
        y1 = data.fields.get("bottom_left_y")
        x2 = data.fields.get("bottom_right_x")
        y2 = data.fields.get("top_left_y")

        point_x = data.fields.get("point_x")
        point_y = data.fields.get("point_y")

        # Scale factor.
        alpha_x = self.configuration.aruco_edge_length / math.sqrt((x1 - x2) ** 2)
        alpha_y = self.configuration.aruco_edge_length / math.sqrt((y1 - y2) ** 2)
        # Careful: distance is calculated in the camera perspective! In our case the y-axis of the gantry is the
        # x-axis of the camera. It is "center_y - point_y" because the image origin is 0/0 in the top left corner
        data.fields["distance_x"] = round(alpha_x * (point_x - center_x), 2)
        data.fields["distance_y"] = round(alpha_y * (center_y - point_y), 2)
        data.fields["scalefactor_x"] = round(alpha_x, 5)
        data.fields["scalefactor_y"] = round(alpha_y, 5)
        return data
