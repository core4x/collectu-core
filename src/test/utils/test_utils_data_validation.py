import unittest
import json
from pathlib import Path

# Internal imports.
import utils.data_validation


class TestUtilsDataValidation(unittest.TestCase):
    """
    This is the test for utils.data_validation.
    """

    def setUp(self):
        """
        This method is called before each test.
        """
        # Load the validation test data.
        with open('./data/test_utils_data_validation/validation_data.json') as json_file:
            self.test_data = json.load(json_file)

    def tearDown(self):
        """
        This method is called after each test.
        """
        pass

    def test_validate_function(self):
        """
        Test the validate function.
        """
        # Check normal case.
        valid, index, messages = utils.data_validation.validate(data={"test1": 1},
                                                                requirements=["(key * with int)"])
        self.assertEqual(True, valid, "Validation should be true but wasn't.")
        self.assertEqual(0, index, "The first requirement (index = 0) should be valid but wasn't.")
        self.assertEqual([{'messages': [], 'requirement': '(key * with int)'}], messages,
                         "The returned message was not as expected.")
        # Check for two requirements, with one valid.
        valid, index, messages = utils.data_validation.validate(data={"test1": 1},
                                                                requirements=["(key * with str)", "(key * with int)"])
        self.assertEqual(True, valid, "Validation should be true but wasn't.")
        self.assertEqual(1, index, "The second requirement (index = 1) should be valid but wasn't.")
        self.assertEqual([{'requirement': '(key * with str)',
                           'messages': ["The value '1' of key 'test1' is not of type str but was int."]},
                          {'requirement': '(key * with int)', 'messages': []}], messages,
                         "The returned message was not as expected.")
        # Check if valid if no requirement is given.
        valid, index, messages = utils.data_validation.validate(data={"test1": 1},
                                                                requirements=[])
        self.assertEqual(True, valid, "Validation should be true but wasn't.")
        self.assertEqual(-1, index, "The index should be -1 since there was no requirement.")
        self.assertEqual([], messages, "The returned message was not as expected.")
        # Check exception generation.
        self.assertRaises(ChildProcessError, utils.data_validation.validate, {"test1": 1}, ["(invalid)"])
        # Check what happens if no data is given.
        valid, index, messages = utils.data_validation.validate(data={},
                                                                requirements=["(key * with int)"])
        self.assertEqual(False, valid, "Validation should be false but wasn't.")
        self.assertEqual(-1, index, "There should be no valid requirement (-1).")
        self.assertEqual([{'requirement': '(key * with int)',
                           'messages': ['There should be at least one key in the data object.']}], messages,
                         "The returned message was not as expected.")

    def test_is_same_data_type_function(self):
        """
        Test the _is_same_data_type function.
        """
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="str", value="string"))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="str", value=1))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="int", value=12))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="int", value=1.2))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="float", value=23.2))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="float", value="string"))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="bool", value=True))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="bool", value=1))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="list", value=[True, 1, "string"]))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="list", value=1))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="list", value=[]))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="numbers", value=[1, 22.2, 34]))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="numbers", value=1))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="strs", value=["1", "2"]))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="strs", value=1))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="bools", value=[True, False]))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="bools", value=1))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="ints", value=[1, 22, 34]))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="ints", value=[1.2, 2]))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="floats", value=[1.3, 22.2, 34.4]))
        self.assertFalse(utils.data_validation._is_same_data_type(data_type="floats", value=[2, 23]))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="numbers", value=[]))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="strs", value=[]))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="bools", value=[]))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="floats", value=[]))
        self.assertTrue(utils.data_validation._is_same_data_type(data_type="ints", value=[]))
        self.assertRaises(Exception, utils.data_validation._is_same_data_type, "unknown_type", "some value")

    def test_format_message(self):
        """
        Test the format_message function.
        """
        formatted_messages = utils.data_validation.format_message([{'requirement': '(key * with str)',
                                                                    'messages': [
                                                                        "The value '1' of key 'test1' is not of type str but was int."]},
                                                                   {'requirement': '(key * with int)', 'messages': []}])
        self.assertEqual(["\n(key * with str): The value '1' of key 'test1' is not of type str but was int."],
                         formatted_messages, "Unexpected output.")

    def test_validation(self):
        """
        Test the data validation logic using test data.
        """
        for data in self.test_data['test_data']:
            valid, index, messages = utils.data_validation.validate(data=data.get("data"),
                                                                    requirements=data.get("requirement"))
            self.assertEqual(data.get("assertion"), valid, f"Validation of requirement '{data.get('requirement')}' "
                                                           f"should be '{data.get('assertion')}' but was "
                                                           f"'{valid}'. Messages: {str(messages)}")


def _valid(data: dict, *requirements: str) -> bool:
    return utils.data_validation.validate(data=data, requirements=list(requirements))[0]


class TestRequirementLanguage(unittest.TestCase):
    """
    The parts of the requirement language the test data above does not cover.
    """

    def test_expressions_are_combined_with_and_or_and_not(self):
        data = {"a": 1, "b": "x"}
        self.assertTrue(_valid(data, "((key a with int) or (key a with str))"))
        self.assertTrue(_valid(data, "((key a with str) or ((key b with str) and (keys == 2)))"))
        self.assertFalse(_valid(data, "((key a with str) or ((key b with str) and (keys == 3)))"))
        self.assertTrue(_valid(data, "(not (key a with str))"))

    def test_a_named_key_has_to_exist(self):
        self.assertTrue(_valid({"a": 1}, "(key a)"))
        self.assertFalse(_valid({"b": 1}, "(key a)"))

    def test_the_number_of_keys_is_compared_with_every_operator(self):
        data = {"a": 1, "b": 2}
        for requirement, expected in (("(keys != 1)", True), ("(keys < 3)", True), ("(keys <= 1)", False),
                                      ("(keys > 1)", True), ("(keys >= 3)", False), ("(keys == 2)", True)):
            with self.subTest(requirement=requirement):
                self.assertEqual(_valid(data, requirement), expected)

    def test_values_are_compared_as_the_literals_they_spell(self):
        data = {"count": 3, "ratio": 0.5, "state": "init", "flag": None}
        self.assertTrue(_valid(data, "(value count > 2)"))
        self.assertTrue(_valid(data, "(value ratio <= 0.5)"))
        self.assertTrue(_valid(data, "(value state == init)"))
        self.assertTrue(_valid(data, "(value state == 'init')"))
        self.assertTrue(_valid(data, "(value flag == None)"))
        self.assertFalse(_valid(data, "(value count == '3')"), "A number is not equal to its text.")

    def test_a_value_of_a_missing_key_is_invalid(self):
        valid, _, messages = utils.data_validation.validate(data={}, requirements=["(value count > 2)"])
        self.assertFalse(valid)
        self.assertEqual(messages[0]["messages"], ["The key 'count' was not found in the data object."])

    def test_the_length_of_every_list_is_compared(self):
        self.assertTrue(_valid({"a": [1, 2], "b": [3, 4]}, "(length * == 2)"))
        self.assertFalse(_valid({"a": [1, 2], "b": 3}, "(length * == 2)"), "A value which is no list has no length.")
        self.assertTrue(_valid({"a": [1], "b": [2, 3]}, "(length * < 3)"))

    def test_lists_of_the_same_length_except_one_key(self):
        self.assertTrue(_valid({"event": "init", "a": [1, 2], "b": [3, 4]}, "(length !event equal)"))
        self.assertFalse(_valid({"event": "init", "a": [1, 2], "b": [3]}, "(length !event equal)"))

    def test_the_length_of_a_value_which_is_no_list_is_invalid(self):
        valid, _, messages = utils.data_validation.validate(data={"a": 1}, requirements=["(length a == 1)"])
        self.assertFalse(valid)
        self.assertEqual(messages[0]["messages"], ["The value of key 'a' should be a list."])

    def test_an_unknown_operator_or_keyword_raises(self):
        for requirement in ("(keys ~ 1)", "(keys == one)", "(value a ~ 1)", "(length * ~ 2)", "(length a ~ 2)",
                            "(length * == two)", "(size a == 1)", "(key a with tuple)", "key a"):
            with self.subTest(requirement=requirement):
                with self.assertRaises(ChildProcessError):
                    utils.data_validation.validate(data={"a": [1]}, requirements=[requirement])

    def test_the_messages_are_flattened_without_duplicates(self):
        messages = [{"requirement": "(key a)", "messages": ["Missing a.", "Missing a."]},
                    {"requirement": "(key b)", "messages": ["Missing b."]},
                    {"requirement": "(key c)", "messages": []}]
        self.assertEqual(utils.data_validation.format_message(messages),
                         ["\n(key a): Missing a.", "\n(key b): Missing b."])


class TestRequirementsAreNoCode(unittest.TestCase):
    """
    The values compared come from the data - an mqtt payload, an opc ua node - and used to be interpolated into an
    expression that was evaluated. A value is only ever compared now, and what is evaluated holds no builtins.
    """

    def test_a_value_is_compared_and_never_run(self):
        # Each of them turned the comparison into something else once it was part of the evaluated expression.
        payloads = ["init' or 'x",
                    "x') or __import__('os').getpid() or ('",
                    '") or __import__("os").getpid() or ("',
                    "__import__('os').getpid()"]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertFalse(_valid({"state": payload}, "(value state == init)"))
                self.assertTrue(_valid({"state": payload}, "(value state != init)"))

    def test_keys_with_brackets_do_not_change_the_requirement(self):
        data = {"a) or (True": 1}
        self.assertFalse(_valid(data, "(key a with int)"))
        self.assertTrue(_valid(data, "(keys == 1)"))

    def test_the_requirement_is_evaluated_without_builtins(self):
        with self.assertRaises(ChildProcessError):
            utils.data_validation.validate(data={"a": 1}, requirements=["(key a) and __import__('os')"])

    def test_the_right_hand_side_is_read_as_a_literal_or_as_text(self):
        self.assertEqual(utils.data_validation._as_literal("3"), 3)
        self.assertEqual(utils.data_validation._as_literal("'3'"), "3")
        self.assertEqual(utils.data_validation._as_literal("init"), "init")
        self.assertEqual(utils.data_validation._as_literal("__import__('os')"), "__import__('os')")

    def test_only_the_comparison_operators_are_applied(self):
        self.assertTrue(utils.data_validation._compare(2, ">=", 2))
        with self.assertRaises(Exception):
            utils.data_validation._compare(2, "is", 2)


if __name__ == '__main__':
    unittest.main()
