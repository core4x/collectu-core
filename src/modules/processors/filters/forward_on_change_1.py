"""
If the key is not found in the fields, the tags are checked. If the key is not found, nothing is forwarded.
"""
from dataclasses import dataclass, field

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
    description: str = "This module forwards the data object (or the defined key) only if a defined key-value changes."
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
        key: str = field(
            metadata=dict(description="The field or tag key whose value is checked for the change. "
                                      "If `*` is given, the complete data object (measurement, fields, and tags) "
                                      "is checked for changes.",
                          required=False,
                          dynamic=True),
            default="*")
        forward_only_key: bool = field(
            metadata=dict(description="Only forward the key which is checked. "
                                      "If the key is `*`, always the complete data object is forwarded on change.",
                          required=False,
                          dynamic=False),
            default=False)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.previous_value = None
        """The previously received value of the key or the hash value of the fields and tags 
        (if the complete data object is checked for changes)."""

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        searched_key = str(self._dyn(self.configuration.key))

        if searched_key != "*":
            value = data.fields.get(searched_key, data.tags.get(searched_key, None))
        else:
            value = hash(frozenset(data.fields.items() | data.tags.items()))

        if value is None:
            # Could not find the key in fields or tags.
            data.fields = {}
        else:
            if value != self.previous_value:
                # The value has changed.
                if self.configuration.forward_only_key and searched_key != "*":
                    # Remove all others.
                    if searched_key in data.fields.keys():
                        data.fields = {searched_key: value}
                    else:
                        data.tags = {searched_key: value}
            else:
                # Nothing has changed. Reset the fields, so it will not be forwarded.
                data.fields = {}
            self.previous_value = value

        return data
