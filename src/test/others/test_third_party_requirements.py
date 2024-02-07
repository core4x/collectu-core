import unittest

# Internal imports.
import utils.plugin_interface


class TestThirdPartyRequirements(unittest.TestCase):
    """
    This is the test for all third party requirements.
    """

    def setUp(self):
        """
        This method is called before each test.
        """
        # Get all required packages from requirements.txt.
        self.app_packages = {}
        with open("../requirements.txt", "r") as requirements_file:
            for line in requirements_file.read().splitlines():
                package_name, version = line.split("==", 1)
                self.app_packages[package_name] = version

    def tearDown(self):
        """
        This method is called after each test.
        """
        pass

    def test_third_party_package_conflicts(self):
        """
        Test if there are conflicts between module requirements and the global app requirements.
        """
        list_of_module_data = utils.plugin_interface.get_plugin_requirement_status()
        for module in list_of_module_data:
            requirements = module.get("requirements", [])
            for requirement in requirements:
                package_name, version = requirement.split("==", 1)
                # Check if the package is also used by the app.
                if package_name in self.app_packages:
                    # If it is also used by the app, check if they use the same version.
                    self.assertEqual(self.app_packages.get(package_name), version,
                                     f"The module '{module.get('name', 'undefined')}' uses a third party "
                                     f"requirement '{package_name}' whose version '{version}' is different "
                                     f"from the version required by the app '{self.app_packages.get(package_name)}'.")
