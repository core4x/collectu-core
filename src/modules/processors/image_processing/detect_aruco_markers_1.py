"""
Markers can be generated using: https://chev.me/arucogen/

This module returns a list of all identified markers, if more than one marker was found.
The list with the key `markers` (fields) contains a dict for every marker with the following information:

- `center_x`: The x coordinate of the center.
- `center_y`: The y coordinate of the center.
- `top_right_x`: The x coordinate of the top right corner.
- `bottom_right_x`: The x coordinate of the bottom right corner.
- `bottom_left_x`: The x coordinate of the bottom left corner.
- `top_left_x`: The x coordinate of the top left corner.
- `top_right_y`: The y coordinate of the top right corner.
- `bottom_right_y`: The y coordinate of the bottom right corner.
- `bottom_left_y`: The y coordinate of the bottom left corner.
- `top_left_y`: The y coordinate of the top left corner.
- `id`: The id of the marker.
- `aruco_type`: The aruco type (e.g. DICT_4X4_50).
- `edge_length_x`: The average edge length of the both x edges.
- `edge_length_y`: The average edge length of the both y edges.
- `edge_length_mean`: The average edge length of the marker.

If only one marker was found, the information are directly put into fields.

In addition, the given image, with the highlighted markers (green), the x axis (yellow),
and the y axis (cyan) is returned with the key `aruco_image`.
"""
import base64
from dataclasses import dataclass, field
from typing import List, Dict, Any

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import OneOf


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = False
    """Is this module public?"""
    description: str = "This module detects aruco markers in a given image."
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
        marker_ids: List[str] = field(
            metadata=dict(description="The list of marker ids which shall be detected. "
                                      "If no ids are given, every marker is extracted.",
                          required=False),
            default_factory=list)
        aruco_type: str = field(
            metadata=dict(description="The type of the marker.",
                          required=False,
                          validate=OneOf(possibilities=["DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_4X4_1000",
                                                        "DICT_5X5_50", "DICT_5X5_100", "DICT_5X5_250", "DICT_5X5_1000",
                                                        "DICT_6X6_50", "DICT_6X6_100", "DICT_6X6_250", "DICT_6X6_1000",
                                                        "DICT_7X7_50", "DICT_7X7_100", "DICT_7X7_250", "DICT_7X7_1000",
                                                        "DICT_ARUCO_ORIGINAL", "DICT_APRILTAG_16h5",
                                                        "DICT_APRILTAG_25h9", "DICT_APRILTAG_36h11"])),
            default="DICT_4X4_50")

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

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {"aruco_type": ["DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_4X4_1000", "DICT_5X5_50",
                               "DICT_5X5_100", "DICT_5X5_250", "DICT_5X5_1000", "DICT_6X6_50", "DICT_6X6_100",
                               "DICT_6X6_250", "DICT_6X6_1000", "DICT_7X7_50", "DICT_7X7_100", "DICT_7X7_250",
                               "DICT_7X7_1000", "DICT_ARUCO_ORIGINAL", "DICT_APRILTAG_16h5", "DICT_APRILTAG_25h9",
                               "DICT_APRILTAG_36h11"]}

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

        ARUCO_DICT = {"DICT_4X4_50": cv2.aruco.DICT_4X4_50,
                      "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
                      "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
                      "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
                      "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
                      "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
                      "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
                      "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
                      "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
                      "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
                      "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
                      "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
                      "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
                      "DICT_7X7_100": cv2.aruco.DICT_7X7_100,
                      "DICT_7X7_250": cv2.aruco.DICT_7X7_250,
                      "DICT_7X7_1000": cv2.aruco.DICT_7X7_1000,
                      "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
                      "DICT_APRILTAG_16h5": cv2.aruco.DICT_APRILTAG_16h5,
                      "DICT_APRILTAG_25h9": cv2.aruco.DICT_APRILTAG_25h9,
                      "DICT_APRILTAG_36h10": cv2.aruco.DICT_APRILTAG_36h10,
                      "DICT_APRILTAG_36h11": cv2.aruco.DICT_APRILTAG_36h11}

        # Load the ArUCo dictionary, grab the ArUCo parameters, and detect the markers.
        aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICT[self.configuration.aruco_type])
        aruco_params = cv2.aruco.DetectorParameters_create()
        (corners, ids, rejected) = cv2.aruco.detectMarkers(image=modified_img,
                                                           dictionary=aruco_dict,
                                                           parameters=aruco_params)

        identified_markers: List[Dict[str, Any]] = []
        """A list containing dicts for every identified marker."""
        if len(corners) > 0:
            # Flatten the aruco ID list.
            ids = ids.flatten()
            # Loop over the detected aruco corners.
            for (marker_corner, marker_id) in zip(corners, ids):
                if self.configuration.marker_ids and marker_id not in self.configuration.marker_ids:
                    continue

                # Extract the marker corners,
                # which are always returned in top-left, top-right, bottom-right, and bottom-left order.
                (top_left, top_right, bottom_right, bottom_left) = marker_corner.reshape((4, 2))
                # Convert each of the (x, y)-coordinate pairs to integers.
                top_right = (round(top_right[0]), round(top_right[1]))
                bottom_right = (round(bottom_right[0]), round(bottom_right[1]))
                bottom_left = (round(bottom_left[0]), round(bottom_left[1]))
                top_left = (round(top_left[0]), round(top_left[1]))

                # Draw the bounding box of the aruco detection.
                cv2.line(modified_img, top_left, top_right, (0, 255, 0), 2)
                cv2.line(modified_img, top_right, bottom_right, (0, 255, 0), 2)
                cv2.line(modified_img, bottom_right, bottom_left, (0, 255, 0), 2)
                cv2.line(modified_img, bottom_left, top_left, (0, 255, 0), 2)
                # Compute and draw the center (x, y)-coordinates of the aruco marker.
                center_x = round((top_left[0] + bottom_right[0]) / 2.0)
                center_y = round((top_left[1] + bottom_right[1]) / 2.0)
                cv2.circle(img=modified_img, center=(center_x, center_y), radius=20, color=(255, 0, 255),
                           thickness=10)
                # Draw the aruco marker ID on the image.
                cv2.putText(modified_img, f"ID: {marker_id}",
                            (top_left[0], top_left[1] - 15), cv2.FONT_HERSHEY_SIMPLEX,
                            1, (0, 255, 0), 2)
                arrow_length = 100
                cv2.arrowedLine(img=modified_img,
                                pt1=(center_x, center_y),
                                pt2=(center_x + arrow_length, center_y),
                                color=(255, 255, 0),
                                thickness=5)
                cv2.arrowedLine(img=modified_img,
                                pt1=(center_x, center_y),
                                pt2=(center_x, center_y + arrow_length),
                                color=(0, 255, 255),
                                thickness=5)

                identified_markers.append({"center_x": center_x,
                                           "center_y": center_y,
                                           "top_right_x": top_right[0],
                                           "top_right_y": top_right[1],
                                           "bottom_right_x": bottom_right[0],
                                           "bottom_right_y": bottom_right[1],
                                           "bottom_left_x": bottom_left[0],
                                           "bottom_left_y": bottom_left[1],
                                           "top_left_x": top_left[0],
                                           "top_left_y": top_left[1],
                                           "id": marker_id,
                                           "aruco_type": self.configuration.aruco_type,
                                           "edge_length_x": abs(sum([top_right[0] - top_left[0],
                                                                     bottom_right[0] - bottom_left[0]]) / 2),
                                           "edge_length_y": abs(sum([bottom_right[1] - top_right[1],
                                                                     bottom_left[1] - top_left[1]]) / 2),
                                           "edge_length_mean": abs(sum([top_right[0] - top_left[0],
                                                                        bottom_right[0] - bottom_left[0],
                                                                        bottom_right[1] - top_right[1],
                                                                        bottom_left[1] - top_left[1]]) / 4)})
        else:
            self.logger.warning("Could not find any markers.")

        if len(identified_markers) == 1:
            # Unpack the list.
            for key, value in identified_markers[0].items():
                data.fields[key] = value
        elif identified_markers:
            data.fields["markers"] = identified_markers

        data.fields["aruco_image"] = base64.b64encode(cv2.imencode('.jpg', modified_img)[1]).decode()
        return data
