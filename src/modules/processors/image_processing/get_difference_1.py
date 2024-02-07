"""
This module calculates the difference between two images.
The first image has to be named `image` and base64 encoded.
"""
import base64
from dataclasses import dataclass, field

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
    description: str = "This module calculates the difference between two images."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["opencv-contrib-python==4.6.0.66", "scikit-image==0.19.3"]
    """Define your requirements here."""
    field_requirements: list[str] = ["(key image with str)"]
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        second_image_name: str = field(
            metadata=dict(description="The name of the second input image.",
                          required=True),
            default="image2")

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
            global structural_similarity
            from skimage.metrics import structural_similarity
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
        # Get and decode both base64 images.
        np_arr = np.frombuffer(base64.b64decode(data.fields.get("image")), np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        np_arr2 = np.frombuffer(base64.b64decode(data.fields.get(self.configuration.second_image_name)), np.uint8)
        img2 = cv2.imdecode(np_arr2, cv2.IMREAD_COLOR)

        # Make the images gray-scale images.
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        # Blur it to minimize noise.
        img = cv2.GaussianBlur(img, (5, 5), 0)
        img2 = cv2.GaussianBlur(img2, (5, 5), 0)

        # Compute SSIM between two images.
        score, diff = structural_similarity(img, img2, full=True)
        # print("Similarity Score: {:.3f}%".format(score * 100))

        # The diff image contains the actual image differences between the two images
        # and is represented as a floating point data type, so we must convert the array
        # to 8-bit unsigned integers in the range [0,255] before we can use it with OpenCV.
        diff = (diff * 255).astype("uint8")

        # Threshold the difference image, followed by finding contours to
        # obtain the regions that differ between the two images.
        thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        contours = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours[0] if len(contours) == 2 else contours[1]

        # Make image color again.
        img = cv2.cvtColor(img, cv2.IMREAD_COLOR)
        img2 = cv2.cvtColor(img2, cv2.IMREAD_COLOR)

        # Highlight differences.
        mask = np.zeros(img.shape, dtype='uint8')
        filled = img2.copy()

        # TODO: Check how this behaves and which contour is taken (why only one?).
        c = contours[0]
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        if area > 100:
            cv2.rectangle(img, (x, y), (x + w, y + h), (36, 255, 12), 2)
            cv2.rectangle(img2, (x, y), (x + w, y + h), (36, 255, 12), 2)
            cv2.drawContours(mask, [c], 0, (0, 255, 0), -1)
            cv2.drawContours(filled, [c], 0, (0, 255, 0), -1)

        data.fields["image"] = base64.b64encode(cv2.imencode('.png', diff)[1]).decode()
        data.fields["image2"] = base64.b64encode(cv2.imencode('.png', img)[1]).decode()
        data.fields["point_x"] = x
        data.fields["point_y"] = y
        return data
