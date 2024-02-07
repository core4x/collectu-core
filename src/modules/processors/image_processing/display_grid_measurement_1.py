"""
This module displays the measured grid structure.

Uses the following field keys:
- `grid_spacing`: As int/float.
- `size_x`: As int/float.
- `size_y`: As int/float.

This module creates the following fields:

"""
from dataclasses import dataclass, field
import base64
from io import BytesIO

# Internal imports.
from models.interfaces import Data
from modules.processors.base.base import AbstractProcessorModule, models
import config


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = False
    """Is this module public?"""
    description: str = "This module creates the gcode for a given grid size."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["pillow==10.0.1"]
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
        ppmm: int = field(
            metadata=dict(description="Pixel per mm",
                          required=True),
            default=5)
        k_start: int = field(
            metadata=dict(description="Start value of k for the first creation of the offset array.",
                          required=True),
            default=1)

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
            global Image
            global ImageDraw
            from PIL import Image, ImageDraw
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def _run(self, data: models.Data) -> Data | bool:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        try:
            k = data.fields.get("k")
            distance_x = data.fields.get("distance_x")
            distance_y = data.fields.get("distance_y")
            gridabs = data.fields.get("gridabs")

            # Switch x and y coordinates to transform to camera perspective
            gridposition_x = gridabs[k][1]
            gridposition_y = - gridabs[k][0]

            # Initiate the array "offsets" to save each loop measurement. The first entry is the offset of the 0/0 laser
            # gcode to the aruco center
            if k == self.configuration.k_start:
                offsets = [[0, 0, distance_x, distance_y]]
            # If the array already exists, append the next measurement while deducing the initial 0/0-Offset from the
            # measured distances
            else:
                offsets = data.fields.get("offsets")
                offset_x = round(distance_x - offsets[0][2], 2)
                offset_y = round(distance_y - offsets[0][3], 2)
                offsets.append([gridposition_x, gridposition_y, gridposition_x + offset_x, gridposition_y + offset_y,
                                offset_x, offset_y])

            # Create a picture with the grid on it. Picture resolution is based on the pixel per mm (ppmm)
            ppmm = self.configuration.ppmm
            # X and Y are switched because the camera x-axis is parallel to the gantry y-
            # The additional space outside of the grid. In multiples of ppmm
            outside_spacing = 5
            width = int((data.fields.get("size_y") + 2 * outside_spacing) * ppmm)
            height = int((data.fields.get("size_x") + 2 * outside_spacing) * ppmm)
            spacing = int(data.fields.get("grid_spacing") * ppmm)

            image = Image.new(mode='RGB', size=(width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)

            # Draw the blue KOS Lines through the center
            line = ((image.width / 2, 0), (image.width / 2, image.height))
            draw.line(line, fill=(0, 191, 255), width=int(ppmm))
            line = ((0, image.height / 2), (image.width, image.height / 2))
            draw.line(line, fill=(0, 191, 255), width=int(ppmm))

            # Draw the vertical lines
            y_start = 0
            y_end = image.height
            for x in range(0, image.width, spacing):
                line = ((x + outside_spacing * ppmm, y_start), (x + outside_spacing * ppmm, y_end))
                draw.line(line, fill=(0, 0, 0), width=int(0.5 * ppmm))

            # Draw the horizontal lines
            x_start = 0
            x_end = image.width
            for y in range(0, image.height, spacing):
                line = ((x_start, y + outside_spacing * ppmm), (x_end, y + outside_spacing * ppmm))
                draw.line(line, fill=(0, 0, 0), width=int(0.5 * ppmm))

            # Draw the points of the measurement into the grid image
            m = 1
            for m in range(len(offsets)):
                radius = ppmm
                box = [(width / 2 + offsets[m][2] * ppmm - radius, height / 2 - offsets[m][3] * ppmm - radius),
                       (width / 2 + offsets[m][2] * ppmm + radius, height / 2 - offsets[m][3] * ppmm + radius)]
                draw.ellipse(box, fill=(255, 0, 0), outline=(0, 0, 0), width=1)

            with BytesIO() as image_binary:
                image.save(image_binary, 'PNG')
                image_binary.seek(0)
                data.fields["image"] = base64.b64encode(image_binary.read()).decode()

            if k == self.configuration.k_start:
                data.fields["offsets"] = offsets
            else:
                data.fields["offsets"] = offsets
                data.fields["offset_x"] = - offset_y  # The offsets have been switched back to gantry orientation
                data.fields["offset_y"] = offset_x  # The offsets have been switched back to gantry orientation

            return data

        except Exception as e:
            self.logger.error("Could not create grid image: {0}".format(str(e)), exc_info=config.EXC_INFO)
