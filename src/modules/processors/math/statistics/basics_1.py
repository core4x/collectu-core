"""
You can either pass one key with a list of integers or floats, or any number of keys,
where the values are integer or float.

Example:

```json
{
    "key": [1, 2.32, 3]
}
```
or
```json
{
    "key1": 1,
    "key2": 2,
    "key3": 3.5
}
```

**Note:** Only the field values are used.

This module calculates and adds the following fields (if enabled):
- `count`
- `sum`
- `mean`
- `median`
- `min`
- `max`
- `stdev`
"""
import os
from dataclasses import dataclass, field
from typing import List
from statistics import mean, median, stdev

# Internal imports.
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
    description: str = "This module calculates basic statistic values of the given field values."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
    """Define your requirements here."""
    field_requirements: list[str] = ['((key * with numbers) and (keys == 1))',
                                     '((key * with int/float) and (keys > 1))', ]
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        add: bool = field(
            metadata=dict(description="Do you want to add the fields created by the processor module to "
                                      "the existing ones, or reset the fields. If you select `add=true` "
                                      "fields are overwritten, if the field name already exists.",
                          required=False),
            default=True)
        count: bool = field(
            metadata=dict(description="Calculate the number of given values.",
                          required=False),
            default=True)
        sum: bool = field(
            metadata=dict(description="Calculate the sum of all given values.",
                          required=False),
            default=True)
        mean: bool = field(
            metadata=dict(description="Calculate the mean value of all given values.",
                          required=False),
            default=True)
        median: bool = field(
            metadata=dict(description="Calculate the median value of all given values.",
                          required=False),
            default=True)
        min: bool = field(
            metadata=dict(description="Find the minimal value of all given values.",
                          required=False),
            default=True)
        max: bool = field(
            metadata=dict(description="Find the maximal value of all given values.",
                          required=False),
            default=True)
        stdev: bool = field(
            metadata=dict(description="Calculate the standard deviation of all given values.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    @classmethod
    def get_test_data(cls) -> List[dict]:
        """
        Provides the test data for processor modules.
        Not every processor modules provides test data.
        The validation functionality is skipped.

        :returns: A list containing test data with the keys:
                  module_config: The configuration of the module as yaml string.
                  input_data: The input data object with measurement, fields and tags.
                  output_data: The expected output data object with measurement, fields and tags.
        """
        test_1 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     add=True),
                  "input_data": models.Data(measurement="test",
                                            fields={"key_0": 78,
                                                    "key_1": 0.873,
                                                    "key_2": 0.108,
                                                    "key_3": 21,
                                                    "key_4": 0.149},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"key_0": 78,
                                                     "key_1": 0.873,
                                                     "key_2": 0.108,
                                                     "key_3": 21,
                                                     "key_4": 0.149,
                                                     "count": 5,
                                                     "sum": 100.13000000000001,
                                                     "mean": 20.026,
                                                     "median": 0.873,
                                                     "min": 0.108,
                                                     "max": 78,
                                                     "stdev": 33.61767620612704},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     add=False,
                                                     median=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"key_0": 78,
                                                    "key_1": 0.873,
                                                    "key_2": 0.108,
                                                    "key_3": 21,
                                                    "key_4": 0.149},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"count": 5,
                                                     "sum": 100.13000000000001,
                                                     "mean": 20.026,
                                                     "min": 0.108,
                                                     "max": 78,
                                                     "stdev": 33.61767620612704},
                                             tags={"test1": 1, "test2": 2})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     add=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"key_0": 78,
                                                    "key_1": 0.873,
                                                    "key_2": 0.108,
                                                    "key_3": 21,
                                                    "key_4": 0.149},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"count": 5,
                                                     "sum": 100.13000000000001,
                                                     "mean": 20.026,
                                                     "median": 0.873,
                                                     "min": 0.108,
                                                     "max": 78,
                                                     "stdev": 33.61767620612704},
                                             tags={"test1": 1, "test2": 2})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     add=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"key_0": [78, 0.873, 0.108, 21, 0.149]},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"count": 5,
                                                     "sum": 100.13000000000001,
                                                     "mean": 20.026,
                                                     "median": 0.873,
                                                     "min": 0.108,
                                                     "max": 78,
                                                     "stdev": 33.61767620612704},
                                             tags={"test1": 1, "test2": 2})}

        test_data = [test_1, test_2, test_3, test_4]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        # If one key, the value should be a list with numbers.
        if len(data.fields) == 1:
            values = next(iter(data.fields.values())).copy()
        # Otherwise, take every value of every entry.
        else:
            values = data.fields.copy().values()

        if not self.configuration.add:
            # Reset the fields.
            data = models.Data(measurement=data.measurement,
                               fields={},
                               tags=data.tags)

        if self.configuration.count:
            data.fields["count"] = len(values)
        if self.configuration.sum:
            data.fields["sum"] = sum(values)
        if self.configuration.mean:
            data.fields["mean"] = mean(values)
        if self.configuration.median:
            data.fields["median"] = median(values)
        if self.configuration.min:
            data.fields["min"] = min(values)
        if self.configuration.max:
            data.fields["max"] = max(values)
        if self.configuration.stdev:
            data.fields["stdev"] = stdev(values)

        return data
