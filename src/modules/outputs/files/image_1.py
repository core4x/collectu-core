"""
This module checks if the key `image` is given and stores the received data of this field.
"""
import os
import threading
from dataclasses import dataclass, field
import pathlib
import datetime
from typing import Dict, Any
import base64

# Internal imports.
import config
from modules.outputs.base.base import AbstractOutputModule, models
from models.validations import OneOf


class OutputModule(AbstractOutputModule):
    """
    Class for the console output module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = False
    """Is this module public?"""
    description: str = "This module stores the received image (base64 encoded) as a file."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["opencv-contrib-python==4.6.0.66"]
    """Define your requirements here."""
    can_be_buffer: bool = False
    """If True, the child has to implement 'store_buffer_data' and 'get_buffer_data'."""

    @dataclass
    class Configuration(models.OutputModule):
        """
        The configuration model of the module.
        """
        filepath: str = field(
            metadata=dict(description="The path.",
                          required=False),
            default="images")
        file_type: str = field(
            metadata=dict(description="The file type. Has to be one of: jpg, jpeg, or png.",
                          required=False,
                          validate=OneOf(["jpg", "jpeg", "png"])),
            default="jpg")
        replace_existing_file: bool = field(
            metadata=dict(description="If the file with the name already exists, it is overwritten. "
                                      "If this is false, a timestamp is added to the filename.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
        super().__init__(configuration=configuration)
        self.dir_path = None
        """The file path."""

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {"file_type": ["jpg", "jpeg", "png"]}

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

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            # This is the file path.
            self.dir_path = os.path.join('..', 'data', '{0}').format(self.configuration.filepath)
            # Create directory.
            pathlib.Path(os.path.join('..', 'data', str(pathlib.Path(self.configuration.filepath)))).mkdir(
                parents=True,
                exist_ok=True)

            # Start the queue processing for storing incoming data.
            threading.Thread(target=self._process_queue,
                             daemon=False,
                             name="Queue_Worker_{0}".format(self.configuration.id)).start()

            self.logger.info("Successfully created or found directory '{0}'.".format(self.dir_path))
            return True

        except Exception as e:
            self.logger.critical("Could not create or find directory '{0}'. {1}"
                                 .format(self.dir_path, str(e)), exc_info=config.EXC_INFO)
            return False

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        try:
            # Get and decode the base64 image.
            if "image" in data.fields:
                np_arr = np.frombuffer(base64.b64decode(data.fields.get("image")), np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if self.configuration.replace_existing_file:
                    filename = f"{data.measurement}.{self.configuration.file_type}"
                else:
                    # Add timestamp to the filename.
                    timestamp = datetime.datetime.utcnow().strftime("%Y_%m_%d %H_%M_%S_%f")
                    filename = f"{timestamp} {data.measurement}.{self.configuration.file_type}"

                if not cv2.imwrite(os.path.join(self.dir_path, filename), img):
                    self.logger.error("Could not write file due to an unknown error.")
        except Exception as e:
            self.logger.error("Something went wrong while trying to write file: {0}."
                              .format(str(e)), exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
