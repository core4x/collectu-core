"""
**Note:**   The starting directory is `data`.

**Note:**   Directories specified in the `filepath` (e.g. `dir1/dir2/test.csv`) are created automatically.

**Note:**   If the file already exists, it is overwritten.

When the csv output module is added to the configuration,
the data changes are saved in the following way in the specified file:

| Timestamp            | Measurement   | Field key   | Field value   | Tag key    | Tag value            |
| :--------------------|:--------------|:------------| :-------------| :----------| :--------------------|
| 10-11-2020 18:21:26  | Rest_client   | level       | INFO          |            |                      |
| 10-11-2020 18:21:26  | Rest_client   |             |               | host       | http://test.com      |

If one measurement has multiple fields or tags, they are written separately in new rows.
"""
import os
import threading
from dataclasses import dataclass, field
import pathlib
import csv

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
    description: str = "This module stores the data in a specified csv file. " \
                       "The created file is compatible with the input module `csv_to_data_object_1`."
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
            metadata=dict(description="The path and file name.",
                          required=False),
            default="csv_file/test.csv")
        include_tags: bool = field(
            metadata=dict(description="Shall tags be saved as well.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
        super().__init__(configuration=configuration)
        self.file_stream = None
        """The file stream."""
        self.writer = None
        """The csv writer instance."""

    def start(self) -> bool:
        """
        Just starts the thread for processing the queue.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            # This is the file path including the file name.
            file = os.path.join('..', 'data', '{0}').format(self.configuration.filepath)
            # Create directory.
            pathlib.Path(os.path.join('..', 'data',
                                      str(pathlib.Path(self.configuration.filepath).parents[0]))).mkdir(
                parents=True,
                exist_ok=True)

            self.file_stream = open(file, 'w', newline='')

            if self.configuration.include_tags:
                fieldnames = ["Timestamp", "Measurement", "Field key", "Field value", "Tag key", "Tag value"]
            else:
                fieldnames = ["Timestamp", "Measurement", "Field key", "Field value"]

            self.writer = csv.DictWriter(self.file_stream, fieldnames=fieldnames)
            self.writer.writeheader()

            # Start the queue processing for storing incoming data.
            threading.Thread(target=self._process_queue,
                             daemon=False,
                             name="Queue_Worker_{0}".format(self.configuration.id)).start()

            self.logger.info("Successfully created file '{0}'.".format(file))
            return True

        except Exception as e:
            self.logger.critical("Could not create file '{0}'. {1}"
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
            # Make new row for each field.
            for field_key, field_value in data.fields.items():
                self.writer.writerow({'Timestamp': data.time.isoformat(),
                                      'Measurement': data.measurement,
                                      'Field key': field_key,
                                      'Field value': field_value})

            # Make new row for each tag.
            if self.configuration.include_tags:
                for tag_key, tag_value in data.tags.items():
                    self.writer.writerow({'Timestamp': data.time.isoformat(),
                                          'Measurement': data.measurement,
                                          'Tag key': tag_key,
                                          'Tag value': tag_value})

            self.file_stream.flush()
        except Exception as e:
            self.logger.error("Something went wrong while trying to store data: {0}."
                              .format(str(e)), exc_info=config.EXC_INFO)
            self._buffer(data=data, invalid=True)
