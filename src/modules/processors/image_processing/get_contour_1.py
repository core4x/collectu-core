"""
This module outputs the image with every found contour (green) and the selected (`index_of_contour` by size)
found contour (red). If no contour is found, nothing happens.
In addition, the following information is generated as fields:

 - `area`: The area of the second-biggest contour.
 - `equivalent_diameter`: The equivalent diameter of the second-biggest contour.
 - `contour`: As nested list (converted from a numpy ndarray - can be recreated using `np.array(contour)`).
"""
import base64
from dataclasses import dataclass, field

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import Range
from models.interfaces import Data


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = False
    """Is this module public?"""
    description: str = "This module extracts the contour from a given image."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["opencv-contrib-python==4.6.0.66"]
    """Define your requirements here."""
    field_requirements: list[str] = ['(key image with str)']
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        index_of_contour: int = field(
            metadata=dict(description="The index of the contour to be selected. Starting by '0'.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=0, exclusive=False)),
            default=2)

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
        # modified_img = img.copy()

        # Make the image a gray-scale image.
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Filter the image (Schwellwert - mittlere helligkeit).
        # Original
        # img = cv2.bilateralFilter(img, 15, 80, 80)
        # ret, img = cv2.threshold(img, 127, 255, 0)

        # ret, img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        # Otsu's thresholding after Gaussian filtering.
        img = cv2.GaussianBlur(img, (5, 5), 0)
        ret3, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Find the contours in the image.
        contours, hierarchy = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)  # cv2.CHAIN_APPROX_SIMPLE

        try:
            # Find the index_of_contour-biggest contour by its area. The biggest is mostly the complete image.
            max_contour = sorted(contours, key=cv2.contourArea)[-self.configuration.index_of_contour]
            # max_contour = max(contours, key=cv2.contourArea)
        except IndexError as e:
            self.logger.error("Could not find contour with the index '{0}'. '{1}' contours are currently available."
                              .format(self.configuration.index_of_contour, str(len(contours))))
            # Return an empty data object which is not forwarded.
            return Data(measurement="", fields={})

        # Make image color again.
        img = cv2.cvtColor(img, cv2.IMREAD_COLOR)

        # Show all (green).
        cv2.drawContours(image=img, contours=contours, contourIdx=-1, color=(0, 255, 0), thickness=5,
                         lineType=cv2.LINE_AA)

        # Show result --> contour with biggest area (red).
        cv2.drawContours(image=img, contours=[max_contour], contourIdx=-1, color=(0, 0, 255), thickness=5,
                         lineType=cv2.LINE_AA)

        # Analyze contour: https://docs.opencv.org/4.x/d1/d32/tutorial_py_contour_properties.html
        area = cv2.contourArea(max_contour)
        data.fields["area"] = area
        equivalent_diameter = np.sqrt(4 * area / np.pi)
        data.fields["equivalent_diameter"] = equivalent_diameter
        data.fields["contour"] = max_contour.tolist()

        data.fields["image"] = base64.b64encode(cv2.imencode('.jpg', img)[1]).decode()
        return data
