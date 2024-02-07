"""
A 3D visualization using babylon.js: https://www.babylonjs.com/
The module expects the mesh name, with the axis and the value, e.g.: mesh_1.x = 12.
The imported mesh names are shown in the console of your browser.
The position (.x, .y, .z) and rotation (in degree) (.a, .b, .c) are applied immediately and is an absolute value.

Workflow for creating glb files using SolidWorks:
1. Simplify and group your 3D model using SolidWorks. A group contains all objects that move together.
2. Hide all groups. Then show one group and export it as an STL file. Repeat until all groups have been exported.
3. Import all exported STL files in Blender.
4. Export the complete model (containing all STL files) as GLB object.
"""
import os
import base64
from dataclasses import dataclass, field

# Internal imports.
import data_layer
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import Range


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the tag module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module creates a 3D visualization on the dashboard."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
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
        dashboard: str = field(
            metadata=dict(description="The dashboard this visualization belongs to.",
                          required=False),
            default="Default")
        width: int = field(
            metadata=dict(description="The width of the dashboard. Has to be between 1 and 12.",
                          required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=8)
        show_event: bool = field(
            metadata=dict(description="If enabled, the dashboard is highlighted if new data is shown.",
                          required=False),
            default=True)
        models_path: str = field(
            metadata=dict(description="The path to a folder containing all .glb models to be visualized.",
                          required=True),
            default=None)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.latest_data = {}
        """Holds the latest data, which is requested by the frontend view."""
        self.encoded_models: dict[str, str] = {}
        """A dictionary containing all models."""
        data_layer.dashboard_modules.append(self)
        """Self register in data layer. This list is used by the frontend view to request the latest data."""
        # Load all models.
        self._encode_glb_files_to_base64()

    def _encode_glb_files_to_base64(self):
        glb_files = [f for f in os.listdir(self.configuration.models_path) if f.endswith('.glb')]
        for glb_file in glb_files:
            file_path = os.path.join(self.configuration.models_path, glb_file)
            with open(file_path, 'rb') as file:
                base64_data = base64.b64encode(file.read()).decode('utf-8')
                self.encoded_models[glb_file] = base64_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        self.latest_data = {"id": self.configuration.id,
                            "dashboard": self.configuration.dashboard,
                            "show_event": self.configuration.show_event,
                            "name": self.configuration.name,
                            "width": self.configuration.width,
                            "description": self.configuration.description,
                            "_models": self.encoded_models,  # If a key starts with an underscore, it is only send once.
                            "type": "3d_viewer",
                            "data": data.__dict__}
        return data
