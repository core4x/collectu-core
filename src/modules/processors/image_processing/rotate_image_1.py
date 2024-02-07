""""""
import base64
from dataclasses import dataclass, field
from typing import Dict, Any

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import OneOf


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    __version__: str = "1.0"
    """The version of the module."""
    __public__: bool = False
    """Is this module public?"""
    __description__: str = "This module rotates a given image."
    """A short description."""
    __author__: str = "Colin Reiff"
    """The author name."""
    __email__: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    __deprecated__: bool = False
    """Is this module deprecated."""
    __third_party_requirements__: list[str] = ["opencv-contrib-python==4.6.0.66"]
    """Define your requirements here."""
    # These requirements are custom validated below.
    __field_requirements__: list[str] = ['(key image with str)']
    """Data validation requirements for the fields dict."""
    __tag_requirements__: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        rotation: str = field(
            metadata=dict(description="The type of the marker.",
                          required=False,
                          validate=OneOf(possibilities=["ROTATE_90_CLOCKWISE", "ROTATE_90_COUNTERCLOCKWISE",
                                                        "ROTATE_180"])),
            default="ROTATE_90_CLOCKWISE")

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {"rotation": ["ROTATE_90_CLOCKWISE", "ROTATE_90_COUNTERCLOCKWISE", "ROTATE_180"]}

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

        # Rotate the image.
        modified_img = cv2.rotate(modified_img, getattr(cv2, self.configuration.rotation))

        data.fields["image"] = base64.b64encode(cv2.imencode('.jpg', modified_img)[1]).decode()
        return data
