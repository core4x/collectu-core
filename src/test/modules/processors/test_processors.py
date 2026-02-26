import unittest
import json
from pathlib import Path

# Internal imports.
import data_layer
import utils.data_validation
import utils.plugin_interface


class TestProcessors(unittest.TestCase):
    """
    This is the test for all available processors.
    """

    def setUp(self):
        """
        This method is called before each test.
        """
        utils.plugin_interface.load_modules()
        # Load the validation test data.
        with open('./data/test_utils_data_validation/validation_data.json') as json_file:
            self.test_data = json.load(json_file)

    def tearDown(self):
        """
        This method is called after each test.
        """
        pass

    def test_processor_modules_requirements(self):
        """
        Test if the given field and tag requirements of the single processor modules are valid.
        """
        for modname, module in data_layer.registered_modules.items():
            if not modname.startswith("processors."):
                continue
            for data in self.test_data['test_data']:
                try:
                    valid, index, messages = utils.data_validation.validate(data=data.get("data"),
                                                                            requirements=getattr(module,
                                                                                                 'field_requirements'))
                except Exception as e:
                    self.fail(f"Validation of requirement '{getattr(module, 'field_requirements')}' "
                              f"of module '{modname}' was not successful. "
                              f"Probably the given requirement is not in the correct format.")
                try:
                    valid, index, messages = utils.data_validation.validate(data=data.get("data"),
                                                                            requirements=getattr(module,
                                                                                                 'tag_requirements'))
                except Exception as e:
                    self.fail(f"Validation of requirement '{getattr(module, 'tag_requirements')}' "
                              f"of module '{modname}' was not successful. "
                              f"Probably the given requirement is not in the correct format.")

    def test_processors(self):
        """
        Test the single processors with the individually provided test data (data validation functionality is skipped).
        """
        for modname, module in data_layer.registered_modules.items():
            if not modname.startswith("processors."):
                continue
            test_data = module.get_test_data()
            for index, data in enumerate(test_data):
                processor_instance = module(configuration=data.get("module_config"))
                processor_instance.start()
                processed_data = processor_instance._run(data.get("input_data"))
                self.assertEqual(getattr(processed_data, "fields"),
                                 getattr(data.get("output_data"), "fields"),
                                 f"Test number '{index}' of '{modname}' failed.")
                self.assertEqual(getattr(processed_data, "tags"),
                                 getattr(data.get("output_data"), "tags"),
                                 f"Test number '{index}' of '{modname}' failed.")
                self.assertEqual(getattr(processed_data, "measurement"),
                                 getattr(data.get("output_data"), "measurement"),
                                 f"Test number '{index}' of '{modname}' failed.")
                processor_instance.stop()


if __name__ == '__main__':
    unittest.main()
