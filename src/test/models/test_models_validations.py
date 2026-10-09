import re
import types
import unittest
from datetime import datetime, timezone
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Tuple, Dict, List, Union, Any, Optional
from unittest import mock

# Internal imports.
import data_layer
import models.validations
from models.validations import ValidationError


class TestConfiguration(unittest.TestCase):
    """
    This is the test the configuration class methods.
    """

    def setUp(self):
        """
        This method is called before each test.
        """
        self.show_validation_messages = False

    def tearDown(self):
        """
        This method is called after each test.
        """
        pass

    def test_validate_module(self):
        """
        Test the module validation functionality.
        """

        @dataclass
        class Module1:
            """
            A test module.
            """
            string: str = field(
                metadata=dict(description="Some required string.",
                              required=True),
                default=None)

        @dataclass
        class Module2:
            """
            A test module.
            """
            integer: int = field(
                metadata=dict(description="Some not required integer.",
                              required=False,
                              dynamic=True),
                default=1)

        @dataclass
        class Module3:
            """
            A test module.
            """
            integer: int = field(
                metadata=dict(description="Some not required integer.",
                              required=False,
                              dynamic=False),
                default=1)
            a_list: List[str] = field(
                metadata=dict(description="A list.",
                              required=False,
                              dynamic=False),
                default_factory=list)
            a_dict: Dict[str, int] = field(
                metadata=dict(description="A dict.",
                              required=False,
                              dynamic=False),
                default_factory=dict)
            an_any: Any = field(
                metadata=dict(description="Can be any.",
                              required=False,
                              dynamic=False),
                default_factory=list)
            an_union: Union[int, float] = field(
                metadata=dict(description="Can be a union of float or int.",
                              required=False,
                              dynamic=False),
                default=1)

        @dataclass
        class Module4:
            """
            A test module.
            """
            tuple: Tuple[int, str] = field(
                metadata=dict(description="Unknown field type.",
                              required=True,
                              dynamic=False),
                default=None)

        @dataclass
        class Module5:
            """
            A test module.
            """
            an_unknown_union: Union[Tuple[int, int]] = field(
                metadata=dict(description="Can be a union of tuple.",
                              required=False,
                              dynamic=False),
                default_factory=tuple)

        # A required attribute is not provided.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module1(**{}))
        if self.show_validation_messages:
            print(cm.exception)
        # Wrong type of value, which can not be converted.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module3(**{"integer": "wrong"}))
        if self.show_validation_messages:
            print(cm.exception)
        # Unknown data type.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module4(**{"tuple": "wrong"}))
        if self.show_validation_messages:
            print(cm.exception)
        # Test Union of wrong type.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module3(**{"an_union": "string"}))
        if self.show_validation_messages:
            print(cm.exception)
        # Test Dict of wrong type.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module3(**{"a_dict": {1: "test"}}))
        if self.show_validation_messages:
            print(cm.exception)
        # Test an unknown Union.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module5(**{"an_unknown_union": (1, 2)}))
        if self.show_validation_messages:
            print(cm.exception)

        # A not required attribute is not provided.
        try:
            models.validations.validate_module(module=Module2(**{}))
        except Exception as e:
            self.fail("A not required attribute is not provided and raised an exception.")
        # If it can be dynamic and is, it should not be type checked.
        try:
            models.validations.validate_module(module=Module2(**{"integer": "${is.dynamic}"}))
        except Exception as e:
            self.fail("A dynamic variable was type checked but shouldn't.")
        # An attribute is provided in the wrong type, but can be converted.
        try:
            models.validations.validate_module(module=Module2(**{"integer": "1"}))
        except Exception as e:
            self.fail("An convertable attribute value raised an exception.")
        # Test List of wrong type, which can be converted. List items should be string.
        try:
            models.validations.validate_module(module=Module3(**{"a_list": [1, 2]}))
        except Exception as e:
            self.fail("An convertable attribute value raised an exception.")
        # Test Any. Everything is allowed.
        try:
            models.validations.validate_module(module=Module3(**{"an_any": (1, 2)}))
        except Exception as e:
            self.fail("An Any raised an exception but shouldn't.")
        # Test Union.
        try:
            models.validations.validate_module(module=Module3(**{"an_union": 2.2}))
        except Exception as e:
            self.fail("An Union raised an exception but shouldn't.")

    def test_validate_module_optional_none(self):
        """
        Test that optional fields without value stay None instead of being converted (e.g. to "None").
        """

        @dataclass
        class Module:
            """
            A test module.
            """
            string: str = field(
                metadata=dict(description="Some not required string.",
                              required=False),
                default=None)
            integer: int = field(
                metadata=dict(description="Some not required integer.",
                              required=False),
                default=None)
            an_union: Union[str, int] = field(
                metadata=dict(description="Some not required union.",
                              required=False),
                default=None)

        module = Module()
        models.validations.validate_module(module=module)
        self.assertIsNone(module.string)
        self.assertIsNone(module.integer)
        self.assertIsNone(module.an_union)

    def test_validate_module_validation_class(self):
        """
        Test that the validation classes of the fields are executed.
        """

        @dataclass
        class Module:
            """
            A test module.
            """
            integer: int = field(
                metadata=dict(description="Some integer.",
                              required=False,
                              dynamic=True,
                              validate=models.validations.Range(max=10)),
                default=1)
            string: str = field(
                metadata=dict(description="Some string.",
                              required=False,
                              validate=models.validations.OneOf(["a", "b"])),
                default=None)

        # Out of range.
        with self.assertRaises(ValidationError):
            models.validations.validate_module(module=Module(integer=999))
        # Out of range after conversion.
        with self.assertRaises(ValidationError):
            models.validations.validate_module(module=Module(integer="999"))
        # Not one of the possibilities.
        with self.assertRaises(ValidationError):
            models.validations.validate_module(module=Module(string="c"))
        # Wrong type is reported once as type error, the validation class is not executed.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module(integer="wrong"))
        self.assertEqual(len(cm.exception.args[0]), 1)

        # Valid values, None and dynamic variables are not validated.
        try:
            models.validations.validate_module(module=Module(integer=5, string="a"))
            models.validations.validate_module(module=Module())
            models.validations.validate_module(module=Module(integer="${is.dynamic}"))
        except Exception as e:
            self.fail(f"A valid value raised an exception: {e}")


def _messages(validation, value, field_name: str = "field") -> list[str]:
    """
    :returns: The messages the validation raises for the value, or an empty list if it is valid.
    """
    try:
        validation.validate(field_name=field_name, value=value)
    except ValidationError as e:
        return e.args[0]
    return []


class TestRange(unittest.TestCase):
    """
    models.validations.Range, which is exclusive unless told otherwise.
    """

    def test_both_limits_are_excluded(self):
        validation = models.validations.Range(min=0, max=10)
        for value in (0.1, 5, 9.9):
            self.assertEqual(_messages(validation, value), [], value)
        for value in (-1, 0, 10, 11):
            self.assertEqual(len(_messages(validation, value)), 1, value)

    def test_both_limits_are_included_if_not_exclusive(self):
        validation = models.validations.Range(min=0, max=10, exclusive=False)
        for value in (0, 5, 10):
            self.assertEqual(_messages(validation, value), [], value)
        for value in (-0.1, 10.1):
            self.assertEqual(len(_messages(validation, value)), 1, value)

    def test_a_lower_limit_alone(self):
        self.assertEqual(_messages(models.validations.Range(min=0), 10 ** 9), [])
        self.assertEqual(len(_messages(models.validations.Range(min=0), 0)), 1)
        self.assertEqual(_messages(models.validations.Range(min=0, exclusive=False), 0), [])
        self.assertEqual(len(_messages(models.validations.Range(min=0, exclusive=False), -1)), 1)

    def test_an_upper_limit_alone(self):
        self.assertEqual(_messages(models.validations.Range(max=0), -(10 ** 9)), [])
        self.assertEqual(len(_messages(models.validations.Range(max=0), 0)), 1)
        self.assertEqual(_messages(models.validations.Range(max=0, exclusive=False), 0), [])
        self.assertEqual(len(_messages(models.validations.Range(max=0, exclusive=False), 1)), 1)

    def test_without_limits_everything_is_valid(self):
        for exclusive in (True, False):
            self.assertEqual(_messages(models.validations.Range(exclusive=exclusive), -(10 ** 9)), [])

    def test_the_message_names_the_field_the_limits_and_the_value(self):
        (message,) = _messages(models.validations.Range(min=1, max=5), 7, field_name="interval")
        for part in ("'interval'", "'1'", "'5'", "'7'"):
            self.assertIn(part, message)


class TestOneOf(unittest.TestCase):
    """
    models.validations.OneOf.
    """

    def test_only_the_possibilities_are_valid(self):
        validation = models.validations.OneOf(["debug", "info"])
        self.assertEqual(_messages(validation, "info"), [])
        (message,) = _messages(validation, "verbose", field_name="level")
        self.assertIn("'level'", message)
        self.assertIn("'verbose'", message)

    def test_every_element_of_a_list_is_checked(self):
        validation = models.validations.OneOf(["debug", "info"])
        self.assertEqual(_messages(validation, ["debug", "info"]), [])
        self.assertEqual(_messages(validation, []), [])
        (message,) = _messages(validation, ["debug", "verbose"])
        self.assertIn("'verbose'", message)


class TestRegex(unittest.TestCase):
    """
    models.validations.Regex, which matches from the beginning of the value.
    """

    def test_the_value_has_to_match(self):
        validation = models.validations.Regex(regex="^[a-z_]+$")
        self.assertEqual(_messages(validation, "line_3"), ["line_3 does not match expected pattern ^[a-z_]+$."])
        self.assertEqual(_messages(validation, "line"), [])

    def test_the_match_starts_at_the_beginning(self):
        validation = models.validations.Regex(regex="[a-z]+")
        self.assertEqual(_messages(validation, "abc1"), [])
        self.assertEqual(len(_messages(validation, "1abc")), 1)

    def test_the_message_can_be_given(self):
        validation = models.validations.Regex(regex=r"\d+", error="{input} is no number ({regex}).")
        self.assertEqual(_messages(validation, "abc"), [r"abc is no number (\d+)."])

    def test_flags_and_compiled_patterns_are_supported(self):
        self.assertEqual(_messages(models.validations.Regex(regex="abc", flags=re.IGNORECASE), "ABC"), [])
        self.assertEqual(_messages(models.validations.Regex(regex=re.compile("abc", re.IGNORECASE)), "ABC"), [])


@dataclass
class _Field:
    """
    A nested configuration, as it is used for a list of fields.
    """
    key: str = field(
        metadata=dict(description="The key.",
                      required=True),
        default=None)
    value: int = field(
        metadata=dict(description="The value.",
                      required=False),
        default=0)

    def __post_init__(self):
        models.validations.validate_module(self)


class TestNestedListClassValidation(unittest.TestCase):
    """
    models.validations.NestedListClassValidation validates each element of a list of nested configurations.
    """

    def setUp(self):
        self.validation = models.validations.NestedListClassValidation(child_class=_Field, child_field_name="fields")

    def test_valid_elements(self):
        self.assertEqual(_messages(self.validation, [{"key": "a", "value": 1}, {"key": "b"}], "fields"), [])
        self.assertEqual(_messages(self.validation, [], "fields"), [])

    def test_the_errors_of_all_elements_are_reported(self):
        messages = _messages(self.validation, [{"value": "x"}, {"key": "b", "value": "y"}], "fields")
        self.assertEqual(len(messages), 3)
        self.assertIn("Missing value for field key (The key.).", messages)

    def test_it_only_validates_its_own_parameter(self):
        (message,) = _messages(self.validation, [], "other")
        self.assertIn("The parameter 'fields' of type 'list' is missing.", message)


class TestFieldTypes(unittest.TestCase):
    """
    What models.validations.validate_module accepts for each type of parameter, and what it converts it to.
    """

    @staticmethod
    def _validate(annotation, value):
        """
        :returns: The value after validation, and the error messages.
        """

        @dataclass
        class Module:
            parameter: annotation = field(
                metadata=dict(description="The parameter.",
                              required=False),
                default=None)

        module = Module(parameter=value)
        try:
            models.validations.validate_module(module)
        except ValidationError as e:
            return module.parameter, e.args[0]
        return module.parameter, []

    def test_a_datetime_is_read_from_iso_8601(self):
        value, messages = self._validate(datetime, "2026-10-01T12:30:00+00:00")
        self.assertEqual((value, messages), (datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc), []))
        self.assertEqual(len(self._validate(datetime, "yesterday")[1]), 1)
        moment = datetime(2026, 1, 1)
        self.assertEqual(self._validate(datetime, moment), (moment, []))

    def test_a_boolean_is_read_from_what_its_text_says(self):
        """
        bool() makes every text but the empty one True, 'false' included.
        """
        for text, expected in (("true", True), ("TRUE", True), ("yes", True), ("on", True), ("1", True),
                               ("false", False), ("False", False), ("no", False), ("off", False), ("0", False),
                               ("", False)):
            with self.subTest(text=text):
                value, messages = self._validate(bool, text)
                self.assertIs(value, expected)
                self.assertEqual(messages, [])
        self.assertEqual(len(self._validate(bool, "maybe")[1]), 1)

    def test_booleans_in_a_list_or_an_optional_are_read_the_same(self):
        self.assertEqual(self._validate(list[bool], ["false", "true"]), ([False, True], []))
        self.assertEqual(self._validate(Optional[bool], "false"), (False, []))

    def test_a_list_is_read_from_its_text(self):
        self.assertEqual(self._validate(list[int], "[1, 2]"), ([1, 2], []))

    def test_a_single_value_becomes_a_list(self):
        self.assertEqual(self._validate(list[str], "ns=2;i=1"), (["ns=2;i=1"], []))

    def test_the_elements_of_a_list_are_converted(self):
        self.assertEqual(self._validate(list[float], [1, "2.5"]), ([1.0, 2.5], []))
        self.assertEqual(len(self._validate(list[int], [1, "two"])[1]), 1)

    def test_a_dict_is_read_from_its_text(self):
        self.assertEqual(self._validate(dict[str, int], "{'a': 1}"), ({"a": 1}, []))

    def test_the_keys_and_values_of_a_dict_are_checked(self):
        self.assertEqual(len(self._validate(dict[str, int], {1: 1})[1]), 1)
        self.assertEqual(len(self._validate(dict[str, int], {"a": "one"})[1]), 1)
        self.assertEqual(self._validate(dict[str, list], {"a": [1]}), ({"a": [1]}, []))

    def test_a_dict_without_type_arguments_takes_any_keys_and_values(self):
        for annotation in (dict, Dict):
            with self.subTest(annotation=annotation):
                self.assertEqual(self._validate(annotation, {"a": 1, 2: [3]}), ({"a": 1, 2: [3]}, []))
                self.assertEqual(self._validate(annotation, "{'a': 1}"), ({"a": 1}, []))

    def test_an_optional_value_is_converted_to_its_type(self):
        for annotation in (Optional[int], int | None, Union[int, None]):
            with self.subTest(annotation=annotation):
                self.assertEqual(self._validate(annotation, "5"), (5, []))
                self.assertEqual(self._validate(annotation, None), (None, []))

    def test_a_union_converts_to_its_first_type(self):
        self.assertEqual(self._validate(int | float, "5"), (5, []))
        self.assertEqual(self._validate(int | float, 2.5), (2.5, []))
        self.assertEqual(len(self._validate(int | float, "five")[1]), 1)

    def test_a_validation_which_fails_unexpectedly_is_reported(self):
        validation = mock.Mock(spec=models.validations.Validation)
        validation.validate.side_effect = TypeError("Unexpected.")

        @dataclass
        class Module:
            parameter: int = field(
                metadata=dict(description="The parameter.",
                              required=False,
                              validate=validation),
                default=1)

        with self.assertRaises(ValidationError) as raised:
            models.validations.validate_module(Module())
        self.assertEqual(raised.exception.args[0], ["Could not validate field parameter with value 1: Unexpected."])


class TestNormalizeUnion(unittest.TestCase):

    def test_unions_of_both_spellings_are_recognized(self):
        for union in (int | None, Optional[int], Union[int, None]):
            with self.subTest(union=union):
                self.assertEqual(models.validations.normalize_union(union), (True, (int, types.NoneType)))

    def test_other_types_are_no_union(self):
        for annotation in (int, list[int], dict[str, int], Any):
            with self.subTest(annotation=annotation):
                self.assertEqual(models.validations.normalize_union(annotation), (False, ()))


def _module(module_id: str, module_name: str, **parameters) -> SimpleNamespace:
    return SimpleNamespace(id=module_id, module_name=module_name, **parameters)


class TestValidateConfiguration(unittest.TestCase):
    """
    models.validations.validate_configuration: what has to hold for the modules of a configuration together.
    """

    def setUp(self):
        saved = data_layer.registered_modules
        self.addCleanup(setattr, data_layer, "registered_modules", saved)
        data_layer.registered_modules = {"outputs.test.buffer_1": SimpleNamespace(can_be_buffer=True),
                                         "outputs.test.collector_1": SimpleNamespace(can_be_buffer=False)}

    def test_a_valid_configuration_has_no_errors(self):
        configuration = [_module("client", "inputs.test.client_1"),
                         _module("tag", "inputs.test.client_1.tag", input_module="client", links=["collector"]),
                         _module("source", "inputs.test.source_1.variable", links=["tag"]),
                         _module("collector", "outputs.test.collector_1")]
        self.assertEqual(models.validations.validate_configuration(configuration), {})
        self.assertEqual(models.validations.validate_configuration([]), {})

    def test_module_ids_are_unique(self):
        errors = models.validations.validate_configuration([_module("a", "inputs.test.client_1"),
                                                            _module("a", "outputs.test.collector_1")])
        self.assertEqual(errors, {"a": ["The module id is not unique."]})

    def test_a_link_leads_to_an_existing_module(self):
        errors = models.validations.validate_configuration(
            [_module("source", "inputs.test.source_1.variable", links=["missing"])])
        self.assertEqual(errors, {"source": ["A linked module with the id 'missing' does not exist."]})

    def test_links_are_a_list(self):
        errors = models.validations.validate_configuration(
            [_module("source", "inputs.test.source_1.variable", links="collector"),
             _module("collector", "outputs.test.collector_1")])
        self.assertEqual(errors, {"source": ["Links have to be given as list."]})

    def test_input_and_variable_modules_can_not_be_linked_to(self):
        """
        They have no input port: they produce data, they do not receive it.
        """
        for target in ("inputs.test.client_1", "inputs.test.client_1.variable"):
            with self.subTest(target=target):
                errors = models.validations.validate_configuration(
                    [_module("processor", "processors.test.multiplier_1", links=["target"]),
                     _module("target", target)])
                self.assertIn("can not be a link", errors["processor"][0])

    def test_the_input_module_exists(self):
        errors = models.validations.validate_configuration(
            [_module("tag", "inputs.test.client_1.tag", input_module="missing")])
        self.assertEqual(errors, {"tag": ["The given input_module 'missing' does not exist."]})

    def test_the_input_module_is_the_one_of_the_same_file(self):
        errors = models.validations.validate_configuration(
            [_module("tag", "inputs.test.client_1.tag", input_module="other"),
             _module("other", "inputs.test.other_1")])
        self.assertEqual(errors, {"tag": ["The given input_module other should be a module with the name "
                                          "inputs.test.client_1, but was inputs.test.other_1."]})

    def test_a_dynamic_variable_refers_to_an_existing_module(self):
        configuration = [_module("source", "inputs.test.source_1.variable", links=["collector"]),
                         _module("collector", "outputs.test.collector_1",
                                 topic="${source.topic}/${env.HIERARCHY_PATH}/${local.measurement}")]
        self.assertEqual(models.validations.validate_configuration(configuration), {})

        configuration[1].topic = "${missing.topic}"
        errors = models.validations.validate_configuration(configuration)
        self.assertEqual(errors, {"collector": ["The module with the id 'missing' of the dynamic variable "
                                                "'${missing.topic}' does not exist."]})

    def test_modules_of_the_same_type_have_the_same_version(self):
        errors = models.validations.validate_configuration(
            [_module("client", "inputs.test.client_1", version=1),
             _module("tag", "inputs.test.client_1.tag", input_module="client", version=2)])
        self.assertEqual(list(errors), ["-"])
        self.assertIn("different versions of a module type (inputs.test.client_1)", errors["-"][0])

    def test_a_buffered_module_needs_a_buffer(self):
        errors = models.validations.validate_configuration(
            [_module("collector", "outputs.test.collector_1", buffered=True)])
        self.assertEqual(errors, {"collector": ["The module shall be buffered, but no buffer module was defined."]})

        self.assertEqual(models.validations.validate_configuration(
            [_module("collector", "outputs.test.collector_1", buffered=True),
             _module("buffer", "outputs.test.buffer_1", is_buffer=True)]), {})

    def test_there_is_at_most_one_buffer(self):
        errors = models.validations.validate_configuration(
            [_module("first", "outputs.test.buffer_1", is_buffer=True),
             _module("second", "outputs.test.buffer_1", is_buffer=True)])
        self.assertEqual(errors, {"second": ["The module 'first' is already defined as buffer. "
                                             "Only one module can be a buffer."]})

    def test_only_a_module_which_can_be_a_buffer_is_one(self):
        errors = models.validations.validate_configuration(
            [_module("collector", "outputs.test.collector_1", is_buffer=True)])
        self.assertEqual(errors, {"collector": ["The module can not be a buffer."]})

    def test_the_buffer_is_not_buffered_itself(self):
        errors = models.validations.validate_configuration(
            [_module("buffer", "outputs.test.buffer_1", is_buffer=True, buffered=True)])
        self.assertEqual(errors, {"buffer": ["The module itself is defined as a buffer and can not be buffered."]})


if __name__ == '__main__':
    unittest.main()
