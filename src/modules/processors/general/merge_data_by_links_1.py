"""
If not all links send data and in the meantime a module sends new data, the newest data is used.
"""
from dataclasses import dataclass, field
import threading
import copy
from collections import deque

# Internal imports.
import data_layer
import models
from modules.processors.base.base import AbstractProcessorModule


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module waits and merges the data of all connected modules."
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
        measurement: str = field(
            metadata=dict(description="The measurement name of the forwarded data object.",
                          required=False,
                          dynamic=True),
            default="Merged data")
        queue_data: bool = field(
            metadata=dict(description="Do you want to queue the received data. "
                                      "If not, the latest data object of a link is used for merging. "
                                      "This means, you will lose all previously data objects, "
                                      "which could not be merged. "
                                      "This is the case, if e.g. one link is as half as slow as another.",
                          required=False,
                          dynamic=False),
            default=True)
        log_warning_message: bool = field(
            metadata=dict(description="Do you want to receive a warning log if a data object of a link is overwritten "
                                      "before merging. Only supported if `queue_data` is false.",
                          required=False,
                          dynamic=False),
            default=False)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.link_data = {}
        """The data of each link."""

    def start(self) -> bool:
        """
        Create a container for the received data from the links.

        :returns: True if successfully started, otherwise false.
        """
        # Initially fill the dict with all existing modules, which link this one.
        for module in data_layer.configuration.configuration_dict:
            if self.configuration.id in module.get("links", []):
                if self.configuration.queue_data:
                    self.link_data[module.get("id")] = deque()
                else:
                    self.link_data[module.get("id")] = None
        return True

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        # Extract the calling module id from the thread name.
        link_id = threading.current_thread().name.replace("Link_", "").split("_to_", 1)[0]
        if self.link_data[link_id] is not None and \
                not self.configuration.queue_data and \
                self.configuration.log_warning_message:
            self.logger.warning("Received newer data! The linked module with the id '{0}' already sent data "
                                "to be merged. Other linked modules have not yet send their data.".format(str(link_id)))

        if self.configuration.queue_data:
            self.link_data[link_id].append(copy.deepcopy(data))  # Add the data object to the queue.
        else:
            self.link_data[link_id] = copy.deepcopy(data)

        # Check if every link send data.
        if not self.configuration.queue_data and None not in self.link_data.values():
            fields = {}
            tags = {}
            for data_object in self.link_data.values():
                fields = copy.deepcopy(fields | data_object.fields)
                tags = copy.deepcopy(tags | data_object.tags)
            # Make a final data object.
            data = models.Data(measurement=self.configuration.measurement,
                               fields=fields,
                               tags=tags)
            # Reset the container.
            for key in self.link_data.keys():
                self.link_data[key] = None
            return data
        elif self.configuration.queue_data and all(self.link_data.values()):
            fields = {}
            tags = {}
            for key in self.link_data.keys():
                data_object = self.link_data[key].popleft()
                fields = copy.deepcopy(fields | data_object.fields)
                tags = copy.deepcopy(tags | data_object.tags)
            # Make a final data object.
            data = models.Data(measurement=self.configuration.measurement,
                               fields=fields,
                               tags=tags)
            return data
        else:
            # Not all links send data.
            return models.Data(measurement="")
