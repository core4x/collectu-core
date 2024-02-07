"""
This module checks every field and tag value if it is a valid json string and data object.
If so, the first found value is deserialized and used.
The complete data object is, if the according fields exist, replaced.
If fields are missing, the old ones are used.
If the value is not a valid json nothing is done.
"""
import datetime
from dataclasses import dataclass, field
import json

# Internal imports.
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
    description: str = "This module converts a json string to a data object."
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
        # TODO: Decide if the old data should be kept or not.
        pass

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        data_object = None
        found = False
        for key, value in data.fields.copy().items():
            if found:
                break
            try:
                loaded_json = json.loads(value)
                if loaded_json is None:
                    continue
                measurement: str = loaded_json.get("measurement", loaded_json.get("Measurement", data.measurement))
                fields: dict = loaded_json.get("fields", loaded_json.get("Fields", data.fields))
                tags: dict = loaded_json.get("tags", loaded_json.get("Tags", data.tags))
                try:
                    time: datetime.datetime = datetime.datetime.fromisoformat(
                        loaded_json.get("time", loaded_json.get("Time")))
                except Exception as e:
                    time: datetime.datetime = data.time
                data_object = models.Data(measurement=measurement, time=time, fields=fields, tags=tags)
                found = True
            except Exception as e:
                # Value is not a valid json.
                continue

        for key, value in data.tags.copy().items():
            if found:
                break
            try:
                loaded_json = json.loads(value)
                if loaded_json is None:
                    continue
                measurement: str = loaded_json.get("measurement", loaded_json.get("Measurement", data.measurement))
                fields: dict = loaded_json.get("fields", loaded_json.get("Fields", data.fields))
                tags: dict = loaded_json.get("tags", loaded_json.get("Tags", data.tags))
                try:
                    time: datetime.datetime = datetime.datetime.fromisoformat(
                        loaded_json.get("time", loaded_json.get("Time")))
                except Exception as e:
                    time: datetime.datetime = data.time
                data_object = models.Data(measurement=measurement, time=time, fields=fields, tags=tags)
                found = True
            except Exception as e:
                # Value is not a valid json.
                continue
        return data_object
