"""
This module checks every field and tag value if it is a valid json string.
If so, the value is deserialized and replaced with the included json.
If the value is not a valid json, it is not touched.

Exemplary input:
```json
{ "fields": {
    "additionalProp1": "{\"name\":\"John\",\"numbers\":[123,456,789],\"age\":30,\"city\":\"New York\"}",
    "additionalProp2": "my value",
    "additionalProp3": "my value"
  }
}
```

Expected output:
```json
{ "fields": {
    "name": "John",
    "numbers": [
      123,
      456,
      789
    ],
    "age": 30,
    "city": "New York",
    "additionalProp2": "my value",
    "additionalProp3": "my value"
  }
}
```

**Note:**   Lists of objects can not be converted. Only lists with a key can be extracted.
"""
import os
from dataclasses import dataclass, field
from typing import List
import json

# Internal imports.
from modules.processors.base.base import AbstractProcessorModule, models


def _flatten_json_1(obj) -> dict:
    """
    Pull all key-value pairs from a nested JSON. Looses all information about the previous structure.

    :param obj: The json object.

    :returns: A dict.
    """
    arr = {}

    def _extract(obj, arr):
        """
        Recursively search for key-values in JSON tree.
        """
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict):
                    _extract(v, arr)
                else:
                    arr[k] = v
        return arr

    results = _extract(obj, arr)
    return results


def _flatten_json_2(obj) -> dict:
    """
    Pull all key-value pairs from a nested JSON and reflect the previous structure in the key name.

    :param obj: The json object.

    :returns: A dict.
    """
    arr = {}

    def _extract(x, name=''):
        if type(x) is dict:
            for a in x:
                _extract(x[a], name + a + '.')
        elif type(x) is list:
            i = 0
            for a in x:
                _extract(a, name + str(i) + '.')
                i += 1
        else:
            arr[name[:-1]] = x

    if type(obj) is dict or type(obj) is list:
        _extract(obj)
    else:
        # It was probably only a string which could be converted by json.loads (e.g.: "12" --> 12).
        raise Exception
    return arr


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module converts a json string to key-value pairs."
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
        reflect_previous_structure_in_key_name: bool = field(
            metadata=dict(description="If false, json keys without a flat value (not an obj, as dict or list) are "
                                      "extracted and discarded. "
                                      "If true, the key name is added to the child key names, e.g. parent.child: 123.",
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
                                                     reflect_previous_structure_in_key_name=False),
                  "input_data": models.Data(measurement="test",
                                            fields={
                                                "additionalProp1": "{\"name\":\"John\",\"numbers\":[123,456,789],\"age\":30,\"city\":\"New York\"}",
                                                "additionalProp2": "my value",
                                                "additionalProp3": "my value"},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"name": "John",
                                                     "numbers": [123, 456, 789],
                                                     "age": 30,
                                                     "city": "New York",
                                                     "additionalProp2": "my value",
                                                     "additionalProp3": "my value"},
                                             tags={"test1": 1, "test2": 2})}
        test_2 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     reflect_previous_structure_in_key_name=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"test3": 1, "test4": 1.234},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test3": 1, "test4": 1.234},
                                             tags={"test1": 1, "test2": 2})}
        test_3 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     reflect_previous_structure_in_key_name=False),
                  "input_data": models.Data(measurement="test",
                                            fields={"key_count": 1},
                                            tags={
                                                "additionalProp1": "{\"name\":\"John\",\"numbers\":[123,456,789],\"age\":30,\"city\":\"New York\"}",
                                                "additionalProp2": "my value",
                                                "additionalProp3": "my value"}),
                  "output_data": models.Data(measurement="test",
                                             fields={"key_count": 1},
                                             tags={"name": "John",
                                                   "numbers": [123, 456, 789],
                                                   "age": 30,
                                                   "city": "New York",
                                                   "additionalProp2": "my value",
                                                   "additionalProp3": "my value"})}
        test_4 = {"module_config": cls.Configuration(module_name=os.path.splitext(os.path.basename(__file__))[0],
                                                     reflect_previous_structure_in_key_name=True),
                  "input_data": models.Data(measurement="test",
                                            fields={
                                                "additionalProp2": "my value",
                                                "additionalProp1": "{\"test\":{\"name\":\"John\"}}",
                                                "additionalProp3": "my value"},
                                            tags={"test1": 1, "test2": 2}),
                  "output_data": models.Data(measurement="test",
                                             fields={"test.name": "John",
                                                     "additionalProp2": "my value",
                                                     "additionalProp3": "my value"},
                                             tags={"test1": 1, "test2": 2})}

        test_data = [test_1, test_2, test_3, test_4]
        return test_data

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        for key, value in data.fields.copy().items():
            try:
                if self.configuration.reflect_previous_structure_in_key_name:
                    fields = _flatten_json_2(json.loads(value))
                else:
                    fields = _flatten_json_1(json.loads(value))
                if not fields:
                    continue
                # Remove the original entry from the dict.
                data.fields.pop(key)
                # Add the deserialized fields (Caution: this is a python 3.9 or greater function).
                data.fields = data.fields | fields
            except Exception as e:
                # Value is not a valid json.
                continue

        for key, value in data.tags.copy().items():
            try:
                if self.configuration.reflect_previous_structure_in_key_name:
                    tags = _flatten_json_2(json.loads(value))
                else:
                    tags = _flatten_json_1(json.loads(value))
                if not tags:
                    continue
                # Remove the original entry from the dict.
                data.tags.pop(key)
                # Add the deserialized tags (Caution: this is a python 3.9 or greater function).
                data.tags = data.tags | tags
            except Exception as e:
                # Value is not a valid json.
                continue

        return data
