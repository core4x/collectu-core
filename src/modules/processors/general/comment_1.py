""""""
from dataclasses import dataclass, field
from typing import Dict, Any

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import OneOf, Range


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module creates a comment on the configuration frontend."
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
        background_color: str = field(
            metadata=dict(description="The background color of the comment. "
                                      "Has to be a valid CSS color name (or Transparent).",
                          required=False,
                          dyamic=False,
                          validate=OneOf(
                              possibilities=["Transparent", "AliceBlue", "AntiqueWhite", "Aqua", "Aquamarine", "Azure",
                                             "Beige", "Bisque", "Black", "BlanchedAlmond", "Blue", "BlueViolet",
                                             "Brown", "BurlyWood", "CadetBlue", "Chartreuse", "Chocolate", "Coral",
                                             "CornflowerBlue", "Cornsilk", "Crimson", "Cyan", "DarkBlue", "DarkCyan",
                                             "DarkGoldenRod", "DarkGray", "DarkGrey", "DarkGreen", "DarkKhaki",
                                             "DarkMagenta", "DarkOliveGreen", "DarkOrange", "DarkOrchid", "DarkRed",
                                             "DarkSalmon", "DarkSeaGreen", "DarkSlateBlue", "DarkSlateGray",
                                             "DarkSlateGrey", "DarkTurquoise", "DarkViolet", "DeepPink", "DeepSkyBlue",
                                             "DimGray", "DimGrey", "DodgerBlue", "FireBrick", "FloralWhite",
                                             "ForestGreen", "Fuchsia", "Gainsboro", "GhostWhite", "Gold", "GoldenRod",
                                             "Gray", "Grey", "Green", "GreenYellow", "HoneyDew", "HotPink", "IndianRed",
                                             "Indigo", "Ivory", "Khaki", "Lavender", "LavenderBlush", "LawnGreen",
                                             "LemonChiffon", "LightBlue", "LightCoral", "LightCyan",
                                             "LightGoldenRodYellow", "LightGray", "LightGrey", "LightGreen",
                                             "LightPink", "LightSalmon", "LightSeaGreen", "LightSkyBlue",
                                             "LightSlateGray", "LightSlateGrey", "LightSteelBlue", "LightYellow",
                                             "Lime", "LimeGreen", "Linen", "Magenta", "Maroon", "MediumAquaMarine",
                                             "MediumBlue", "MediumOrchid", "MediumPurple", "MediumSeaGreen",
                                             "MediumSlateBlue", "MediumSpringGreen", "MediumTurquoise",
                                             "MediumVioletRed", "MidnightBlue", "MintCream", "MistyRose", "Moccasin",
                                             "NavajoWhite", "Navy", "OldLace", "Olive", "OliveDrab", "Orange",
                                             "OrangeRed", "Orchid", "PaleGoldenRod", "PaleGreen", "PaleTurquoise",
                                             "PaleVioletRed", "PapayaWhip", "PeachPuff", "Peru", "Pink", "Plum",
                                             "PowderBlue", "Purple", "RebeccaPurple", "Red", "RosyBrown", "RoyalBlue",
                                             "SaddleBrown", "Salmon", "SandyBrown", "SeaGreen", "SeaShell", "Sienna",
                                             "Silver", "SkyBlue", "SlateBlue", "SlateGray", "SlateGrey", "Snow",
                                             "SpringGreen", "SteelBlue", "Tan", "Teal", "Thistle", "Tomato",
                                             "Turquoise", "Violet", "Wheat", "White", "WhiteSmoke", "Yellow",
                                             "YellowGreen"])),
            default="Transparent")
        text_color: str = field(
            metadata=dict(description="The text color of the comment. "
                                      "Has to be a valid CSS color name.",
                          required=False,
                          dyamic=False,
                          validate=OneOf(
                              possibilities=["Transparent", "AliceBlue", "AntiqueWhite", "Aqua", "Aquamarine", "Azure",
                                             "Beige", "Bisque", "Black", "BlanchedAlmond", "Blue", "BlueViolet",
                                             "Brown", "BurlyWood", "CadetBlue", "Chartreuse", "Chocolate", "Coral",
                                             "CornflowerBlue", "Cornsilk", "Crimson", "Cyan", "DarkBlue", "DarkCyan",
                                             "DarkGoldenRod", "DarkGray", "DarkGrey", "DarkGreen", "DarkKhaki",
                                             "DarkMagenta", "DarkOliveGreen", "DarkOrange", "DarkOrchid", "DarkRed",
                                             "DarkSalmon", "DarkSeaGreen", "DarkSlateBlue", "DarkSlateGray",
                                             "DarkSlateGrey", "DarkTurquoise", "DarkViolet", "DeepPink", "DeepSkyBlue",
                                             "DimGray", "DimGrey", "DodgerBlue", "FireBrick", "FloralWhite",
                                             "ForestGreen", "Fuchsia", "Gainsboro", "GhostWhite", "Gold", "GoldenRod",
                                             "Gray", "Grey", "Green", "GreenYellow", "HoneyDew", "HotPink", "IndianRed",
                                             "Indigo", "Ivory", "Khaki", "Lavender", "LavenderBlush", "LawnGreen",
                                             "LemonChiffon", "LightBlue", "LightCoral", "LightCyan",
                                             "LightGoldenRodYellow", "LightGray", "LightGrey", "LightGreen",
                                             "LightPink", "LightSalmon", "LightSeaGreen", "LightSkyBlue",
                                             "LightSlateGray", "LightSlateGrey", "LightSteelBlue", "LightYellow",
                                             "Lime", "LimeGreen", "Linen", "Magenta", "Maroon", "MediumAquaMarine",
                                             "MediumBlue", "MediumOrchid", "MediumPurple", "MediumSeaGreen",
                                             "MediumSlateBlue", "MediumSpringGreen", "MediumTurquoise",
                                             "MediumVioletRed", "MidnightBlue", "MintCream", "MistyRose", "Moccasin",
                                             "NavajoWhite", "Navy", "OldLace", "Olive", "OliveDrab", "Orange",
                                             "OrangeRed", "Orchid", "PaleGoldenRod", "PaleGreen", "PaleTurquoise",
                                             "PaleVioletRed", "PapayaWhip", "PeachPuff", "Peru", "Pink", "Plum",
                                             "PowderBlue", "Purple", "RebeccaPurple", "Red", "RosyBrown", "RoyalBlue",
                                             "SaddleBrown", "Salmon", "SandyBrown", "SeaGreen", "SeaShell", "Sienna",
                                             "Silver", "SkyBlue", "SlateBlue", "SlateGray", "SlateGrey", "Snow",
                                             "SpringGreen", "SteelBlue", "Tan", "Teal", "Thistle", "Tomato",
                                             "Turquoise", "Violet", "Wheat", "White", "WhiteSmoke", "Yellow",
                                             "YellowGreen"])),
            default="Black")
        width: int = field(
            metadata=dict(description="The width of the comment in pixel. "
                                      "Can only be initially set or manipulated by resizing the element "
                                      "on the frontend.",
                          required=False,
                          dyamic=False,
                          validate=Range(min=0, exclusive=True)),
            default=10)
        height: int = field(
            metadata=dict(description="The height of the comment in pixel. "
                                      "Can only be initially set or manipulated by resizing the element "
                                      "on the frontend.",
                          required=False,
                          dyamic=False,
                          validate=Range(min=0, exclusive=True)),
            default=10)

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
        return {
            "background_color": ["Transparent", "AliceBlue", "AntiqueWhite", "Aqua", "Aquamarine", "Azure", "Beige",
                                 "Bisque", "Black", "BlanchedAlmond", "Blue", "BlueViolet", "Brown", "BurlyWood",
                                 "CadetBlue", "Chartreuse", "Chocolate", "Coral", "CornflowerBlue", "Cornsilk",
                                 "Crimson", "Cyan", "DarkBlue", "DarkCyan", "DarkGoldenRod", "DarkGray",
                                 "DarkGrey", "DarkGreen", "DarkKhaki", "DarkMagenta", "DarkOliveGreen",
                                 "DarkOrange", "DarkOrchid", "DarkRed", "DarkSalmon", "DarkSeaGreen",
                                 "DarkSlateBlue", "DarkSlateGray", "DarkSlateGrey", "DarkTurquoise",
                                 "DarkViolet", "DeepPink", "DeepSkyBlue", "DimGray", "DimGrey", "DodgerBlue",
                                 "FireBrick", "FloralWhite", "ForestGreen", "Fuchsia", "Gainsboro", "GhostWhite",
                                 "Gold", "GoldenRod", "Gray", "Grey", "Green", "GreenYellow", "HoneyDew",
                                 "HotPink", "IndianRed", "Indigo", "Ivory", "Khaki", "Lavender", "LavenderBlush",
                                 "LawnGreen", "LemonChiffon", "LightBlue", "LightCoral", "LightCyan",
                                 "LightGoldenRodYellow", "LightGray", "LightGrey", "LightGreen", "LightPink",
                                 "LightSalmon", "LightSeaGreen", "LightSkyBlue", "LightSlateGray",
                                 "LightSlateGrey", "LightSteelBlue", "LightYellow", "Lime", "LimeGreen", "Linen",
                                 "Magenta", "Maroon", "MediumAquaMarine", "MediumBlue", "MediumOrchid", "MediumPurple",
                                 "MediumSeaGreen", "MediumSlateBlue", "MediumSpringGreen", "MediumTurquoise",
                                 "MediumVioletRed", "MidnightBlue", "MintCream", "MistyRose", "Moccasin", "NavajoWhite",
                                 "Navy", "OldLace", "Olive", "OliveDrab", "Orange", "OrangeRed", "Orchid",
                                 "PaleGoldenRod", "PaleGreen", "PaleTurquoise", "PaleVioletRed", "PapayaWhip",
                                 "PeachPuff", "Peru", "Pink", "Plum", "PowderBlue", "Purple", "RebeccaPurple", "Red",
                                 "RosyBrown", "RoyalBlue", "SaddleBrown", "Salmon", "SandyBrown", "SeaGreen",
                                 "SeaShell", "Sienna", "Silver", "SkyBlue", "SlateBlue", "SlateGray", "SlateGrey",
                                 "Snow", "SpringGreen", "SteelBlue", "Tan", "Teal", "Thistle", "Tomato", "Turquoise",
                                 "Violet", "Wheat", "White", "WhiteSmoke", "Yellow", "YellowGreen"],
            "text_color": ["Transparent", "AliceBlue", "AntiqueWhite", "Aqua", "Aquamarine", "Azure", "Beige",
                           "Bisque", "Black", "BlanchedAlmond", "Blue", "BlueViolet", "Brown", "BurlyWood",
                           "CadetBlue", "Chartreuse", "Chocolate", "Coral", "CornflowerBlue", "Cornsilk",
                           "Crimson", "Cyan", "DarkBlue", "DarkCyan", "DarkGoldenRod", "DarkGray",
                           "DarkGrey", "DarkGreen", "DarkKhaki", "DarkMagenta", "DarkOliveGreen",
                           "DarkOrange", "DarkOrchid", "DarkRed", "DarkSalmon", "DarkSeaGreen",
                           "DarkSlateBlue", "DarkSlateGray", "DarkSlateGrey", "DarkTurquoise",
                           "DarkViolet", "DeepPink", "DeepSkyBlue", "DimGray", "DimGrey", "DodgerBlue",
                           "FireBrick", "FloralWhite", "ForestGreen", "Fuchsia", "Gainsboro", "GhostWhite",
                           "Gold", "GoldenRod", "Gray", "Grey", "Green", "GreenYellow", "HoneyDew",
                           "HotPink", "IndianRed", "Indigo", "Ivory", "Khaki", "Lavender", "LavenderBlush",
                           "LawnGreen", "LemonChiffon", "LightBlue", "LightCoral", "LightCyan",
                           "LightGoldenRodYellow", "LightGray", "LightGrey", "LightGreen", "LightPink",
                           "LightSalmon", "LightSeaGreen", "LightSkyBlue", "LightSlateGray",
                           "LightSlateGrey", "LightSteelBlue", "LightYellow", "Lime", "LimeGreen", "Linen",
                           "Magenta", "Maroon", "MediumAquaMarine", "MediumBlue", "MediumOrchid", "MediumPurple",
                           "MediumSeaGreen", "MediumSlateBlue", "MediumSpringGreen", "MediumTurquoise",
                           "MediumVioletRed", "MidnightBlue", "MintCream", "MistyRose", "Moccasin", "NavajoWhite",
                           "Navy", "OldLace", "Olive", "OliveDrab", "Orange", "OrangeRed", "Orchid",
                           "PaleGoldenRod", "PaleGreen", "PaleTurquoise", "PaleVioletRed", "PapayaWhip",
                           "PeachPuff", "Peru", "Pink", "Plum", "PowderBlue", "Purple", "RebeccaPurple", "Red",
                           "RosyBrown", "RoyalBlue", "SaddleBrown", "Salmon", "SandyBrown", "SeaGreen",
                           "SeaShell", "Sienna", "Silver", "SkyBlue", "SlateBlue", "SlateGray", "SlateGrey",
                           "Snow", "SpringGreen", "SteelBlue", "Tan", "Teal", "Thistle", "Tomato", "Turquoise",
                           "Violet", "Wheat", "White", "WhiteSmoke", "Yellow", "YellowGreen"]}

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        return data
