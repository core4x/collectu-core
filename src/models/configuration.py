"""
The models are used for the deserialization of the configuration file.
"""
from dataclasses import dataclass, field
import string
import random

# Internal imports.
import models.validations


@dataclass
class Module:
    """
    The base module class.

    Every not required field has to provide a default value.
    """
    id: str = field(
        metadata=dict(description="The unique id of the module.",
                      required=False),
        default=''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(19)))
    module_name: str = field(
        metadata=dict(description="The name of the module.",
                      required=True),
        default=None)
    version: int = field(
        metadata=dict(description="The version of the module.",
                      required=False),
        default=0)
    active: bool = field(
        metadata=dict(description="Is this module active.",
                      required=False),
        default=True)
    name: str = field(
        metadata=dict(description="The user-specific name of the module.",
                      required=False),
        default="")
    description: str = field(
        metadata=dict(description="The description of the module.",
                      required=False),
        default="")
    panel: str = field(
        metadata=dict(description="The panel where the module is placed.",
                      required=False,
                      validate=models.validations.OneOf(["panel-1", "panel-2", "panel-3", "panel-4", "panel-5"])),
        default="panel-1")
    x: int = field(
        metadata=dict(description="The x position of the module on the canvas.",
                      required=False),
        default=0)
    y: int = field(
        metadata=dict(description="The y position of the module on the canvas.",
                      required=False),
        default=0)

    def __post_init__(self):
        models.validations.validate_module(self)


@dataclass
class ProcessorModule(Module):
    """
    The abstract ProcessorModule class.
    """
    links: list[str] = field(
        metadata=dict(description="The links of this module.",
                      required=False),
        default_factory=list)


@dataclass
class TagModule(Module):
    """
    The abstract TagModule class.
    """
    is_tag: bool = field(
        metadata=dict(description="Boolean indicating if the data is to be stored as a tags.",
                      required=False),
        default=False)
    is_field: bool = field(
        metadata=dict(description="Boolean indicating if the data is to be stored as fields.",
                      required=False),
        default=True)
    links: list[str] = field(
        metadata=dict(description="The links of this module.",
                      required=False),
        default_factory=list)


@dataclass
class VariableModule(Module):
    """
    The abstract VariableModule class.
    """
    links: list[str] = field(
        metadata=dict(description="The links of this module.",
                      required=False),
        default_factory=list)
    measurement: str = field(
        metadata=dict(description="The measurement name.",
                      required=False),
        default="test")


@dataclass
class InputModule(Module):
    """
    The abstract InputModule class.
    """
    pass


@dataclass
class OutputModule(Module):
    """
    The abstract OutputModule class.
    """
    buffered: bool = field(
        metadata=dict(description="If true, data is buffered, when the output module is not accessible. "
                                  "An output module with is_buffer is `True` has to be configured.",
                      required=False),
        default=False)
    is_buffer: bool = field(
        metadata=dict(description="Is this output module a buffer. "
                                  "Module attribute can_be_buffer has to be `True`. "
                                  "Exactly one buffer can be configured.",
                      required=False),
        default=False)
