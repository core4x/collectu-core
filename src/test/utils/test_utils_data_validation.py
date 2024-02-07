import unittest
import json

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


if __name__ == '__main__':
    unittest.main()
