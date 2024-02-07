"""
This module outputs the following information as fields:

- `angle_deg`: The angle in degrees.
- `center_x`: The x coordinate of the center.
- `center_y`: The y coordinate of the center.
- `image`: The given image with the drawn coordinate system.
"""
import base64
from dataclasses import dataclass
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
    public: bool = False
    """Is this module public?"""
    description: str = "This module applies a principal component analysis on a given contour."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["scikit-learn==1.1.2", "opencv-contrib-python==4.6.0.66"]
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
            global cv2
            import cv2
            global np
            import numpy as np
            global PCA
            from sklearn.decomposition import PCA
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

        contour = np.array(data.fields.get("contour"))
        X = np.empty((len(contour), 2))
        for j, pt in enumerate(contour):
            X[j] = pt

        pca = PCA(n_components=2)
        pca.fit(X)
        comp = pca.components_
        var = pca.explained_variance_
        mean = pca.mean_
        angle_rad = math.atan2(comp[0, 1], comp[0, 0])  # Orientation in radians.
        angle_deg = (-np.rad2deg(angle_rad) - 90)  # Orientation in degrees.
        center = (round(mean[0]), round(mean[1]))

        cv2.circle(modified_img, center, 20, (255, 0, 255), 10)
        self._draw_axis(img=modified_img,
                        p_=center,
                        q_=(center[0] + 0.02 * comp[0, 0] * var[0], center[1] + 0.02 * comp[0, 1] * var[0]),
                        color=(255, 255, 0),
                        scale=0.6)
        self._draw_axis(img=modified_img,
                        p_=center,
                        q_=(center[0] - 0.02 * comp[1, 0] * var[1], center[1] - 0.02 * comp[1, 1] * var[1]),
                        color=(0, 0, 255),
                        scale=0.6)

        data.fields["angle_deg"] = angle_deg
        data.fields["center_x"] = mean[0]
        data.fields["center_y"] = mean[1]
        data.fields["image"] = base64.b64encode(cv2.imencode('.jpg', modified_img)[1]).decode()
        return data

    def _draw_axis(self, img, p_, q_, color=(0, 0, 255), scale=0.6):
        """
        Draw axis on the given image.

        :param img: The image.
        :param p_: Start point.
        :param q_: End point.
        :param color: The color.
        :param scale; Tge length factor of the arrows.
        """
        p = list(p_)
        q = list(q_)

        angle = math.atan2(p[1] - q[1], p[0] - q[0])  # Angle in radians.
        hypotenuse = math.sqrt((p[1] - q[1]) * (p[1] - q[1]) + (p[0] - q[0]) * (p[0] - q[0]))

        # Here we lengthen the arrow by a factor of scale.
        q[0] = p[0] - scale * hypotenuse * math.cos(angle)
        q[1] = p[1] - scale * hypotenuse * math.sin(angle)
        cv2.line(img, (round(p[0]), round(p[1])), (round(q[0]), round(q[1])), color, 10, cv2.LINE_AA)

        # Create the arrow hooks.
        p[0] = q[0] + 9 * math.cos(angle + math.pi / 4)
        p[1] = q[1] + 9 * math.sin(angle + math.pi / 4)
        cv2.line(img, (round(p[0]), round(p[1])), (round(q[0]), round(q[1])), color, 10, cv2.LINE_AA)

        p[0] = q[0] + 9 * math.cos(angle - math.pi / 4)
        p[1] = q[1] + 9 * math.sin(angle - math.pi / 4)
        cv2.line(img, (round(p[0]), round(p[1])), (round(q[0]), round(q[1])), color, 10, cv2.LINE_AA)
