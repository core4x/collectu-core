"""
This module creates two csv files containing a table with the measured offsets in bit values.

**Note:**   The starting directory is `data`.

**Note:**   Directories specified in the `filepath` (e.g. `dir1/dir2/test.csv`) are created automatically.

**Note:**   If the file already exists, it is overwritten.
"""
from dataclasses import dataclass, field

# Internal imports.
import config
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
    third_party_requirements: list[str] = ["numpy==1.22.3"]
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
        filepath: str = field(
            metadata=dict(description="The path to the folder, where the two csv files are stored.",
                          required=False),
            default="offset_tables")

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
        # TODO: Define the field requirements.
        size_x = data.fields.get("size_x")
        size_y = data.fields.get("size_y")
        grid_spacing = data.fields.get("grid_spacing")

        # Create the empty table.
        offsets = data.fields.get("offsets")
        x = size_x / grid_spacing + 1  # +1 because if size_x = 100 and grid_spacing = 50 -> 2 but 3 are points needed
        y = size_y / grid_spacing + 1
        cols, rows = (int(x + 1), int(y + 1))  # +1 because there is a header row.
        bit_table_x = [[0 for i in range(cols)] for j in range(rows)]  # Create empty 2d array.
        bit_table_y = [[0 for i in range(cols)] for j in range(rows)]  # Create empty 2d array.

        # Create the heading of the correction table for the bit-values -> e.g. 0, 8192, .... 65535
        x = 0
        x_max = int(size_x / grid_spacing)
        while x in range(x_max + 1):
            s = x / x_max * 65535
            bit_table_x[0][x + 1] = int(s)
            x = x + 1

        # Create the side numbers -> e.g. 0, 8192, .... 65535
        y = 0
        y_max = int(size_y / grid_spacing)
        while y in range(y_max + 1):
            s = y / y_max * 65535
            bit_table_x[y + 1][0] = int(s)
            y = y + 1

        # Do the same for the y bit table.
        # Create the heading of the correction table for the bit-values -> e.g. 0, 8192, .... 65535
        x = 0
        x_max = int(size_x / grid_spacing)
        while x in range(x_max + 1):
            s = x / x_max * 65535
            bit_table_y[0][x + 1] = int(s)
            x = x + 1

        # Create the side numbers -> e.g. 0, 8192, .... 65535
        y = 0
        y_max = int(size_y / grid_spacing)
        while y in range(y_max + 1):
            s = y / y_max * 65535
            bit_table_y[y + 1][0] = int(s)
            y = y + 1

        # Fill the table with the offset numbers.
        # Note that we have to switch x and y back from the image coordinates.
        # Start at 2nd row of "offsets" because the first row contains the initial offset.
        k = 1
        while k in range(len(offsets)):
            y = int((offsets[k][0] + size_x / 2) / grid_spacing)
            x = int((-offsets[k][1] + size_x / 2) / grid_spacing)
            bit_table_x[y + 1][x + 1] = int(offsets[k][5] / size_x * 65535)  # Multiply the offset with scaling factor.
            k = k + 1

        # Do the same for the y-coordinates. Not sure if there should be a minus before the bit_table_y values.
        k = 1
        while k in range(len(offsets)):
            y = int((offsets[k][0] + size_x / 2) / grid_spacing)
            x = int((-offsets[k][1] + size_x / 2) / grid_spacing)
            bit_table_y[y + 1][x + 1] = int(- offsets[k][4] / size_x * 65535)  # Multiply the offset with scaling factor
            k = k + 1

        # Save to text file.
        np.savetxt(self.configuration.filepath + r'\bit_table_x.csv', bit_table_x, fmt='%d', delimiter=",")
        np.savetxt(self.configuration.filepath + r'\bit_table_y.csv', bit_table_y, fmt='%d', delimiter=",")

        data.fields["bit_table_x"] = bit_table_x
        data.fields["bit_table_y"] = bit_table_y
        return data
