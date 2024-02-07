"""
This module creates the coordinates for a gcode based on the grid size. Is used for the f-theta-lens laser calibration.

Uses the following field keys:
- `grid_spacing`: As int/float.
- `size_x`: As int/float.
- `size_y`: As int/float.

This module creates the following fields:
- `gridcoordinates`: Complete Gcode array for the grid. Must be converted into individual gcode segments
- `grid_spacing`: Spacing of the grid.
- `size_x`: Size of the grid in x.
- `size_y`: Size of the grid in y.
"""
from dataclasses import dataclass, field

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
import config


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module creates the gcode for a given grid size."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    field_requirements: list[str] = ["((key k with int/float))"]
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """

        grid_spacing: float = field(
            metadata=dict(description="The spacing between the grid cells in mm",
                          required=True),
            default=20)
        size_x: float = field(
            metadata=dict(description="The length of the grid in X in mm. Must be a multiple of the grid spacing",
                          required=True),
            default=80)
        size_y: float = field(
            metadata=dict(description="The length of the grid in Y in mm. Must be a multiple of the grid spacing",
                          required=True),
            default=80)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    def _run(self, data: models.Data):
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """

        k = int(data.fields.get("k"))
        f = self.configuration.size_x / self.configuration.grid_spacing
        h = self.configuration.size_y / self.configuration.grid_spacing
        if not f.is_integer:
            self.logger.error("grid_spacing is not a multiple of size_x: ", f)
        if not h.is_integer:
            self.logger.error("grid_spacing is not a multiple of size_y: ", h)

        # Todo: Check if x and y are not switched.

        # Calculate absolute grid coordinates
        gridabs = [[0, 0], [0, 0]]  # For initial offset
        y = -0.5 * self.configuration.size_y
        while y <= self.configuration.size_y * 0.5:
            x = -0.5 * self.configuration.size_x
            while x <= self.configuration.size_x * 0.5:
                gridabs.append([x, y])
                x = x + self.configuration.grid_spacing
            y = y + self.configuration.grid_spacing

        # Calculate relative Movements
        gridrel = [[0, 0]]
        s = 1

        while s < len(gridabs):
            xrel = gridabs[s][0] - gridabs[s - 1][0]
            yrel = gridabs[s][1] - gridabs[s - 1][1]
            gridrel.append([xrel, yrel])
            s = s + 1

        data.fields["k_max"] = len(gridrel)
        data.fields["base_x"] = gridrel[k][0]
        data.fields["base_y"] = gridrel[k][1]
        data.fields["gridrel"] = gridrel
        data.fields["gridabs"] = gridabs
        data.fields["laser_x"] = - gridrel[k][0]
        data.fields["laser_y"] = - gridrel[k][1]
        data.fields["size_x"] = self.configuration.size_x
        data.fields["size_y"] = self.configuration.size_y
        data.fields["grid_spacing"] = self.configuration.grid_spacing
        return data
