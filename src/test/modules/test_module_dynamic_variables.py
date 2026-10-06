"""
Dynamic variables: '${env.NAME}', '${local.key}' and '${module_id.key}' in a parameter, resolved by a module with
AbstractModule._dyn while it runs.
"""
import os
import unittest
from datetime import datetime
from types import SimpleNamespace

# Internal imports.
import data_layer
import models
from modules.base.base import AbstractModule, DynamicVariableException
from test.helpers import GlobalStateTestCase


class _Module(AbstractModule):
    pass


class TestDynamicVariables(GlobalStateTestCase):

    def setUp(self):
        super().setUp()
        os.environ["COLLECTU_TEST_PORT"] = "4840"
        self.module = _Module(SimpleNamespace(id="module", module_name="processors.test.module_1", active=True))
        source = models.Data(measurement="pressure", fields={"value": 7, "zero": 0, "nodes": "[1, 2]"},
                             tags={"site": "Stuttgart"})
        data_layer.module_data["source"] = SimpleNamespace(latest_data=source)
        data_layer.module_data["silent"] = SimpleNamespace(latest_data=None)

    def _dyn(self, value, data_type=None):
        return self.module._dyn(value, data_type)

    def _raises(self, value, data_type=None) -> str:
        with self.assertRaises(DynamicVariableException) as raised:
            self._dyn(value, data_type)
        return str(raised.exception)

    def test_a_value_without_variables_is_returned_as_it_is(self):
        self.assertEqual(self._dyn("hello"), "hello")
        self.assertEqual(self._dyn(5), 5)

    def test_the_text_of_a_list_or_dict_becomes_one(self):
        self.assertEqual(self._dyn("[1, 2]"), [1, 2])
        self.assertEqual(self._dyn("{'a': 1}"), {"a": 1})

    def test_an_environment_variable(self):
        self.assertEqual(self._dyn("${env.COLLECTU_TEST_PORT}"), 4840)

    def test_a_missing_environment_variable_raises(self):
        self.assertIn("Could not find key 'COLLECTU_TEST_UNSET' in environment variables.",
                      self._raises("${env.COLLECTU_TEST_UNSET}"))

    def test_a_field_or_tag_of_the_latest_data_of_another_module(self):
        self.assertEqual(self._dyn("${source.value}"), 7)
        self.assertEqual(self._dyn("${source.site}"), "Stuttgart")
        self.assertEqual(self._dyn("${source.nodes}"), [1, 2])

    def test_a_value_which_is_falsy_is_found(self):
        self.assertEqual(self._dyn("${source.zero}"), 0)

    def test_what_another_module_does_not_have_raises(self):
        self.assertIn("Could not find key 'missing' in fields or tags.", self._raises("${source.missing}"))
        self.assertIn("Could not find module with the id 'unknown'.", self._raises("${unknown.value}"))
        self.assertIn("Referenced module has no latest data.", self._raises("${silent.value}"))

    def test_the_data_object_being_processed(self):
        moment = datetime(2026, 10, 1)
        self.module.current_input_data = models.Data(measurement="temperature", fields={"value": 21.5},
                                                     tags={"unit": "C"}, time=moment)
        self.assertEqual(self._dyn("${local.value}"), 21.5)
        self.assertEqual(self._dyn("${local.unit}"), "C")
        self.assertEqual(self._dyn("${local.measurement}"), "temperature")
        self.assertEqual(self._dyn("${local.time}"), moment)
        self.assertIn("Could not find key 'missing' in fields or tags.", self._raises("${local.missing}"))

    def test_local_without_a_data_object_being_processed_raises(self):
        self.assertIn("Only tag, output, and processor modules support 'local'.", self._raises("${local.value}"))

    def test_variables_inside_a_text_are_replaced(self):
        self.module.current_input_data = models.Data(measurement="temperature")
        self.assertEqual(self._dyn("${source.site}/${local.measurement}:${env.COLLECTU_TEST_PORT}"),
                         "Stuttgart/temperature:4840")

    def test_a_single_variable_keeps_the_type_of_its_value(self):
        self.assertEqual(self._dyn("${source.value}"), 7)
        self.assertEqual(self._dyn("v${source.value}"), "v7")

    def test_a_text_starting_with_a_variable_and_ending_with_a_brace_is_kept(self):
        self.assertEqual(self._dyn("${source.site}\n{% for key in data %}{{ key }}{% endfor %}"),
                         "Stuttgart\n{% for key in data %}{{ key }}{% endfor %}")
        self.assertEqual(self._dyn("${source.site} {'a': 1}"), "Stuttgart {'a': 1}")

    def test_the_value_is_converted_to_the_given_type(self):
        self.assertEqual(self._dyn("${source.value}", "str"), "7")
        self.assertEqual(self._dyn("${source.value}", "float"), 7.0)
        self.assertIsInstance(self._dyn("${source.value}", "float"), float)
        self.assertEqual(self._dyn("${env.COLLECTU_TEST_PORT}", "int"), 4840)
        self.assertEqual(self._dyn("{'a': 1}", "dict"), {"a": 1})
        self.assertIs(self._dyn("False", "bool"), False)
        self.assertIs(self._dyn("0", "bool"), False)

    def test_a_value_becomes_a_list_if_one_is_asked_for(self):
        self.assertEqual(self._dyn("${source.value}", "list"), [7])
        self.assertEqual(self._dyn("[1, 2]", "list"), [1, 2])

    def test_the_first_type_which_fits_is_taken(self):
        self.assertEqual(self._dyn("${source.site}", ["float", "str"]), "Stuttgart")
        self.assertEqual(self._dyn("${source.value}", ["float", "str"]), 7.0)

    def test_types_are_named_case_insensitively(self):
        self.assertEqual(self._dyn("7", "INT"), 7)
        self.assertEqual(self._dyn("7", "Str"), "7")

    def test_a_value_which_does_not_fit_the_type_raises(self):
        self.assertIn("Could not convert dynamic variable 'Stuttgart' to one of the given data types: int.",
                      self._raises("${source.site}", "int"))

    def test_an_unknown_type_raises(self):
        self.assertIn("Unknown data type tuple.", self._raises("7", "tuple"))

    def test_an_incomplete_marker_raises(self):
        self.assertIn("Found an incomplete marker", self._raises("${env.COLLECTU_TEST_PORT"))


if __name__ == '__main__':
    unittest.main()
