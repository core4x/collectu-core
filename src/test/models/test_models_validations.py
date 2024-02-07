import unittest
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Union, Any

# Internal imports.
from configuration import Configuration
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
        # If it is dynamic but can't be, it should be type checked.
        with self.assertRaises(ValidationError) as cm:
            models.validations.validate_module(module=Module3(**{"integer": "${is.dynamic}"}))
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

    def test_validate_configuration(self):
        """
        Test the configuration validation functionality.
        """
        # Read configuration file with unknown dynamic variable ids.
        with open('data/test_models_validations/wrong_dynamic_variable_ids.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'1': [
            "The module with the id 'unknown_id' of the dynamic variable '${unknown_id.some_key}' does not exist."]},
            errors, "Wrong or none error message generated.")

        # Read configuration file with unknown input_module.
        with open('data/test_models_validations/unknown_input_module.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'some_id_2': ["The given input_module 'wrong_id' does not exist."]},
                         errors, "Wrong or none error message generated.")

        # Read configuration file with wrong input_module module_name.
        with open('data/test_models_validations/wrong_input_module_type.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'some_id_2': [
            'The given input_module some_id_1 should be a module with the name inputs.web.rest_endpoint_1, but was inputs.web.rest_get_1.']},
            errors, "Wrong or none error message generated.")

        # Read configuration with unknown link id.
        with open('data/test_models_validations/unknown_link_id.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'1': ["A linked module with the id 'unknown_link' does not exist."]},
                         errors, "Wrong or none error message generated.")

        # Read configuration with linked modules, which can no be linked (InputModule and VariableModule).
        with open('data/test_models_validations/wrong_linked_module_type.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'1': [
            "The given link with the id 'some_id_1' can not be a link. Input and variable modules have no input port."]},
            errors, "Wrong or none error message generated.")

        # Read configuration with multiple buffer modules.
        with open('data/test_models_validations/multiple_buffer_modules.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'id_2': ["The module 'id_1' is already defined as buffer. Only one module can be a buffer."]},
                         errors, "Wrong or none error message generated.")

        # Read configuration with wrong buffer module.
        with open('data/test_models_validations/wrong_buffer_module.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'id_1': ['The module can not be a buffer.']},
                         errors, "Wrong or none error message generated.")

        # Read configuration with a buffered buffer module.
        with open('data/test_models_validations/buffered_buffer_module.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'id_1': ['The module itself is defined as a buffer and can not be buffered.']},
                         errors, "Wrong or none error message generated.")

        # Read configuration with a buffered module but no buffer was configured.
        with open('data/test_models_validations/no_buffer_module.yml') as config_file:
            content = config_file.read()
        configuration, configuration_dict, errors = Configuration.validate_configuration_from_stream(
            content=content)
        self.assertEqual({'id_1': ['The module shall be buffered, but no buffer module was defined.']},
                         errors, "Wrong or none error message generated.")


if __name__ == '__main__':
    unittest.main()
