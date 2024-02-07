import unittest
import os

# Internal imports.
import utils.plugin_interface
import data_layer
import configuration


class TestModelsConfiguration(unittest.TestCase):
    """
    This is the test for the configuration class methods.
    """

    def setUp(self):
        """
        This method is called before each test.
        """
        # Set the environment variables to control the behaviour of the configuration.
        os.environ["AUTO_START"] = "0"
        os.environ["CONFIG"] = "configuration.yml"
        os.environ["IGNORE_START_FAIL"] = "0"
        os.environ["TEST"] = "0"
        # Load all modules.
        utils.plugin_interface.load_modules()
        # Initialize the configuration.
        data_layer.configuration = configuration.Configuration()

    def tearDown(self):
        """
        This method is called after each test.
        """
        data_layer.configuration.stop()

    def test_to_load_valid_configuration(self):
        """
        Test the loading of a valid configuration stream.
        """
        with open('data/test_models_configuration/valid_configuration.yml') as config_file:
            messages = data_layer.configuration.load_configuration_from_stream(config_file.read())
            if messages:
                self.fail("The loading of the configuration should not raise any error messages.")
        data_layer.configuration.stop()

    def test_to_load_invalid_configuration(self):
        """
        Test the loading of an invalid configuration stream.
        """
        with open('data/test_models_configuration/invalid_configuration.yml') as config_file:
            messages = data_layer.configuration.load_configuration_from_stream(config_file.read())
            if not messages:
                self.fail("An error message should be generated but wasn't.")
        data_layer.configuration.stop()

    def test_restart(self):
        """
        Test a restart.
        """
        self.assertTrue(data_layer.configuration.restart())

    def test_stop(self):
        """
        Test a stop.
        """
        self.assertTrue(data_layer.configuration.stop())

    def test_add_modules_to_configuration(self):
        """
        Test to add modules to the running configuration.
        """
        with open('data/test_models_configuration/1_configuration.yml') as config_file:
            messages = data_layer.configuration.add_modules_to_configuration(config_file.read())
        with open('data/test_models_configuration/2_configuration.yml') as config_file:
            messages = data_layer.configuration.add_modules_to_configuration(config_file.read())
        for module in data_layer.configuration.configuration:
            self.assertTrue(module.id in ["1", "2", "3"])
        data_layer.configuration.stop()

    def test_remove_modules_from_configuration(self):
        """
        Test to remove modules from the running configuration.
        """
        with open('data/test_models_configuration/valid_configuration.yml') as config_file:
            messages = data_layer.configuration.add_modules_to_configuration(config_file.read())
        self.assertTrue("kox222je9x3e1957odm" in [module.id for module in data_layer.configuration.configuration])
        data_layer.configuration.remove_modules_from_configuration(["kox222je9x3e1957odm"])
        self.assertTrue("kox222je9x3e1957odm" not in [module.id for module in data_layer.configuration.configuration])
        data_layer.configuration.stop()

    def test_update_configuration(self):
        """
        Test to update the configuration (removing old and starting new/changed modules).
        """
        # Start a default configuration.
        with open('data/test_models_configuration/valid_configuration.yml') as config_file:
            messages = data_layer.configuration.load_configuration_from_stream(config_file.read())
        # Update with another configuration (contains new modules and others are removed).
        # 1. Removed module with id 'koy6msagn46thviuq9o'.
        # 2. Removed id 'koy6msagn46thviuq9o' from 'links' of module with id 'kox222je9x3e1957odm'.
        # 3. Added new module with id 'added_module_1'.
        with open('data/test_models_configuration/changed_valid_configuration.yml') as config_file:
            messages = data_layer.configuration.update_configuration(config_file.read())
        self.assertTrue("added_module_1" in [module.id for module in data_layer.configuration.configuration])
        self.assertTrue("koy6msagn46thviuq9o" not in [module.id for module in data_layer.configuration.configuration])
        self.assertTrue("koy6msagn46thviuq9o" not in next(filter(lambda module: module.id == "kox222je9x3e1957odm",
                                                                 data_layer.configuration.configuration)).links)
        data_layer.configuration.stop()


if __name__ == '__main__':
    unittest.main()
