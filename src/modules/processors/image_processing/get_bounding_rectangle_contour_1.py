"""
The bounding rectangle is drawn with minimum area, so it considers the rotation also.

Returns the following information as fields:

- `image`: The base64 encoded image with the drawn bounding rectangle (green), the x axis (yellow), and the y axis (cyan).
- `center_x`: The x coordinate of the center of the rectangle.
- `center_y`: The y coordinate of the center of the rectangle.
- `width`: The width of the rectangle.
- `height`: The height of the rectangle.
"""
import base64
import math
from dataclasses import dataclass

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = False
    """Is this module public?"""
    description: str = "This module extracts the minimal bounding rectangle from a given contour."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["opencv-contrib-python==4.6.0.66"]
    """Define your requirements here."""
    field_requirements: list[str] = ['((key contour) and (key image with str))']
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        pass

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
        # Get and decode the base64 image.
        np_arr = np.frombuffer(base64.b64decode(data.fields.get("image")), np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Copy the original image in order to keep the color. This copy is later forwarded.
        modified_img = img.copy()

        # Convert the contour to numpy and get bounding rectangle.
        rect = cv2.minAreaRect(np.array(data.fields.get("contour")))
        (center_x, center_y), (width, height), angle_of_rotation = rect
        box = np.int0(cv2.boxPoints(rect))

        # Show rotated rectangle (green).
        cv2.drawContours(image=modified_img, contours=[box], contourIdx=0, color=(255, 0, 0), thickness=5,
                         lineType=cv2.LINE_AA)
        cv2.circle(img=modified_img, center=(round(center_x), round(center_y)), radius=20, color=(255, 0, 255),
                   thickness=10)
        arrow_length = 100
        cv2.arrowedLine(img=modified_img,
                        pt1=(round(center_x), round(center_y)),
                        pt2=(round(center_x) + round(math.cos(math.radians(angle_of_rotation)) * arrow_length),
                             round(center_y) + round(math.sin(math.radians(angle_of_rotation)) * arrow_length)),
                        color=(255, 255, 0),
                        thickness=5)
        cv2.arrowedLine(img=modified_img,
                        pt1=(round(center_x), round(center_y)),
                        pt2=(round(center_x) + round(math.cos(math.radians(angle_of_rotation + 90)) * arrow_length),
                             round(center_y) + round(math.sin(math.radians(angle_of_rotation + 90)) * arrow_length)),
                        color=(0, 255, 255),
                        thickness=5)

        data.fields["angle_of_rotation"] = round(angle_of_rotation)
        data.fields["center_x"] = round(center_x)
        data.fields["center_y"] = round(center_y)
        data.fields["width"] = round(width)
        data.fields["height"] = round(height)

        data.fields["image"] = base64.b64encode(cv2.imencode('.jpg', modified_img)[1]).decode()
        return data
