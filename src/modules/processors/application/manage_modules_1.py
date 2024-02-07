"""
If a module shall be started (event: start), you have to provide the `configuration` as a valid json or yaml string.

If a module shall be stopped (event: stop), you have to provide the `id` of the module.
If a module with the given id doesn't exist, it is ignored.

The module returns a dictionary with the key `errors` as field with the module ids as key and a list of occurred
configuration errors during the start-up phase (no runtime errors).

fields:
```
{
    "errors": {"the_module_id_123": ["First error.", "Second error."]}
}
```
"""
from dataclasses import dataclass, field
import time
import string
import random

# Internal imports.
import data_layer
from modules.processors.base.base import AbstractProcessorModule, models
from models.validations import Range

# Third party imports.
import yaml
import json


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module starts or stops a given module."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    field_requirements: list[str] = ['((value event == start) and (key configuration with str))',
                                     '((value event == stop) and (key id with str))']
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        execute_module_once: bool = field(
            metadata=dict(description="After the execution (`forward_data_object` has to be true), "
                                      "the module is stopped after a waiting time.",
                          required=False,
                          dynamic=False),
            default=True)
        waiting_time_before_stopping: int = field(
            metadata=dict(description="The waiting time in seconds before stopping the module after its execution. "
                                      "Only applied if `execute_module_once` is true.",
                          required=False,
                          dynamic=False,
                          validate=Range(min=1, exclusive=False)),
            default=5)
        forward_data_object: bool = field(
            metadata=dict(description="If a module is started (event: start), it is directly called by this module. "
                                      "The data object, without the fields `event` and `configuration` is forwarded "
                                      "to the module (except for variable modules).",
                          required=False,
                          dynamic=False),
            default=True)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        if data.fields.get("event") == "start":
            configuration = yaml.load(stream=data.fields.get("configuration"), Loader=yaml.FullLoader)
            # We add an id, if it is not given in the configuration.
            if "id" not in configuration.keys():
                module_id: str = ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(19))
                configuration["id"] = module_id
            else:
                module_id: str = configuration.get("id")

            errors = data_layer.configuration.add_modules_to_configuration(content=json.dumps([configuration]))
            self.logger.info("Successfully started module '{0}' with id '{1}'."
                             .format(configuration.get("module_name"), module_id))

            if self.configuration.forward_data_object:
                # Forward the data object if it is not a variable module.
                if not data_layer.module_data.get(module_id).configuration.module_name.endswith(".variable"):
                    # Remove the both fields for this module.
                    data.fields.pop("event")
                    data.fields.pop("configuration")
                    # Execute the created module.
                    data_layer.module_data.get(module_id).instance.run(data=data)
                if self.configuration.execute_module_once:
                    time.sleep(self.configuration.waiting_time_before_stopping)
                    # Stop the created module.
                    errors = data_layer.configuration.remove_modules_from_configuration(module_ids=[module_id])
                    self.logger.info("Successfully stopped module '{0}' with id '{1}'."
                                     .format(configuration.get("module_name"), module_id))

        elif data.fields.get("event") == "stop":
            errors = data_layer.configuration.remove_modules_from_configuration(module_ids=[data.fields.get("id")])
            self.logger.info("Successfully stopped module with id '{0}'."
                             .format(data.fields.get("id")))
        else:
            # This should never happen, since we already catch it with our field requirements.
            raise Exception("Unknown event '{0}'.".format(data.fields.get("event")))

        data = models.Data(measurement=data.measurement,
                           fields={"errors": errors})

        return data
