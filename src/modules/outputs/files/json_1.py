"""
The generated json file is not a valid json!
Each line is a valid json, but not the complete file.

**Note:**   The starting directory is `data` (for relative paths). But you can also provide an absolut path.

**Note:**   If the file with the name `filepath` already exists, new entries are added at the end of the file.

**Note:**   Directories specified in the `filepath` (e.g. `dir1/dir2/test.json`) are created automatically.

When the JSON file output module is added to the configuration,
the data changes are saved in the following way in the specified file:

```json
{
  "measurement": "measurement",
  "tags": {"level": "INFO", "module": "excel_output_module"},
  "time": "2020-11-27 09:58:23.017578",
  "fields": {"level": "INFO", "module": "excel_output_module"}
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
    description: str = "This module stores the data in a specified file in json format. " \
                       "The created file is compatible with the input module `json_file_to_data_object_1`."
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
                          required=False),
            default="json_file/test.json")

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
        super().__init__(configuration=configuration)
        self.file_stream = None
        """The file stream."""

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            if os.path.isabs(self.configuration.filepath):
                file = self.configuration.filepath
                # Create directory.
                pathlib.Path(os.path.join(str(pathlib.Path(self.configuration.filepath).parents[0]))).mkdir(
                    parents=True,
                    exist_ok=True)
            else:
                # This is the file path including the file name.
                file = os.path.join('..', 'data', '{0}').format(self.configuration.filepath)
                # Create directory.
                pathlib.Path(os.path.join('..', 'data',
                                          str(pathlib.Path(self.configuration.filepath).parents[0]))).mkdir(
                    parents=True,
                    exist_ok=True)
            # Open the file in 'appending' mode. Start writing to the end of the file.
            self.file_stream = open(file, 'a')

            # Start the queue processing for storing incoming data.
            threading.Thread(target=self._process_queue,
                             daemon=False,
                             name="Queue_Worker_{0}".format(self.configuration.id)).start()

            self.logger.info("Successfully created and/or opened file '{0}'.".format(file))
            return True

        except Exception as e:
            self.logger.critical("Could not create or open file '{0}': {1}"
                                 .format(self.configuration.filepath, str(e)),
                                 exc_info=config.EXC_INFO)
            return False

    def stop(self):
        """
        Method for stopping the output module. Is called by the main thread.
        """
        self.file_stream.close()

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
        """
        try:
            # data.time = data.time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            data.time = data.time.isoformat()
            self.file_stream.write('{0}\n'.format(json.dumps(data.__dict__, default=str)))
            self.file_stream.flush()
        except Exception as e:
            self.logger.error("Something went wrong while trying to store data: {0}."
                              .format(str(e)),
                              exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
