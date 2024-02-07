"""
Each data object is stored and the file reset.
Fields and tags are unpacked. Tag keys are overwritten by fields, if they already exist.

**Note:**   The starting directory is `data`.

**Note:**   Directories specified in the `filepath` (e.g. `dir1/dir2/test.json`) are created automatically.

When the JSON file output module is added to the configuration,
the data changes are saved in the following way in the specified file:

```json
{
  "measurement": "measurement",
  "tag_key_1": "value",
  "time": "2020-11-27 09:58:23.017578",
  "field_key_1": "value"
}
```
"""
import os
import threading
from dataclasses import dataclass, field
import pathlib
import json

# Internal imports.
import config
from modules.outputs.base.base import AbstractOutputModule, models


class OutputModule(AbstractOutputModule):
    """
    Class for the console output module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module stores the data in a specified file in json format."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    can_be_buffer: bool = False
    """If True, the child has to implement 'store_buffer_data' and 'get_buffer_data'."""

    @dataclass
    class Configuration(models.OutputModule):
        """
        The configuration model of the module.
        """
        filepath: str = field(
            metadata=dict(description="The path and file name. Can be relative to the data directory or absolut.",
                          required=False,
                          dynamic=True),
            default="json_file/test.json")

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
        super().__init__(configuration=configuration)

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            # Start the queue processing for storing incoming data.
            threading.Thread(target=self._process_queue,
                             daemon=False,
                             name="Queue_Worker_{0}".format(self.configuration.id)).start()

            self.logger.info("Successfully started the processing.")
            return True
        except Exception as e:
            self.logger.critical("Could not start processing: {0}"
                                 .format(str(e)), exc_info=config.EXC_INFO)
            return False

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        try:
            filepath = self._dyn(self.configuration.filepath, data_type="str")
            if os.path.isabs(filepath):
                file = filepath
                # Create directory.
                pathlib.Path(os.path.join(str(pathlib.Path(filepath).parents[0]))).mkdir(
                    parents=True,
                    exist_ok=True)
            else:
                # This is the file path including the file name.
                file = os.path.join('..', 'data', '{0}').format(filepath)
                # Create directory.
                pathlib.Path(os.path.join('..', 'data', str(pathlib.Path(filepath).parents[0]))).mkdir(
                    parents=True,
                    exist_ok=True)

            # Open the file. Start writing to the end of the file.
            with open(file, 'w+') as f:
                json_data = {"time": data.time.isoformat(), "measurement": data.measurement}
                for key, value in data.tags.items():
                    json_data[key] = value
                for key, value in data.fields.items():
                    json_data[key] = value
                f.write('{0}\n'.format(json.dumps(json_data, default=str)))
        except Exception as e:
            self.logger.error("Something went wrong while trying to store data: {0}."
                              .format(str(e)),
                              exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
