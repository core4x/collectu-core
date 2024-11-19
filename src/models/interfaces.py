"""
Models used for interfaces and similar things.
"""
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Data:
    """
    This is the data object transferred between all modules.
    """
    measurement: str = field(
        metadata=dict(description="The measurement name.",
                      required=True))
    fields: dict[str, Any] = field(
        metadata=dict(description="The fields.",
                      required=False),
        default_factory=dict)
    time: datetime = field(
        metadata=dict(description="The timestamp.",
                      required=False),
        default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, Any] = field(
        metadata=dict(description="The tags.",
                      required=False),
        default_factory=dict)


@dataclass
class ModuleData:
    """
    This is the data object used for storing module data.
    """
    module_name: str = field(
        metadata=dict(description="The name of the module.",
                      required=True))
    configuration: Any = field(
        metadata=dict(description="The configuration of the module.",
                      required=True))
    instance: Optional[Any] = field(
        metadata=dict(description="The module instance.",
                      required=False),
        default=None)
    latest_data: Optional[Data] = field(
        metadata=dict(description="The latest processed data object.",
                      required=False),
        default=None)
    latest_log: Optional[Data] = field(
        metadata=dict(description="The latest recorded log in form of a data object.",
                      required=False),
        default=None)


@dataclass
class Log:
    """
    This is the data object for a simplified log message.
    """
    level: str = field(
        metadata=dict(description="The level of the log (INFO, WARNING, ERROR, CRITICAL).",
                      required=True))
    message: str = field(
        metadata=dict(description="The log message.",
                      required=True))
    module: str = field(
        metadata=dict(description="The module name.",
                      required=True))
    name: str = field(
        metadata=dict(description="The file name.",
                      required=True))
    time: str = field(
        metadata=dict(description="The timestamp.",
                      required=True))


@dataclass
class MothershipData:
    """
    This is the data object used for storing mothership data of the reporting apps.
    """
    status: str = field(
        metadata=dict(description="The status of the reporting app. Can be: unknown, running, or inactive.",
                      required=True))
    description: str = field(
        metadata=dict(description="The description of the reporting app.",
                      required=True))
    version: str = field(
        metadata=dict(description="The current version of the reporting app.",
                      required=True))
    last_update: datetime = field(
        metadata=dict(description="The datetime of the last update.",
                      required=False),
        default_factory=lambda: datetime.now(timezone.utc))
    configuration: list[Any] = field(
        metadata=dict(description="The configuration of the reporting app.",
                      required=False),
        default_factory=list)
    latest_logs: list[Log] = field(
        metadata=dict(description="The latest logs of the reporting app.",
                      required=False),
        default_factory=list)
