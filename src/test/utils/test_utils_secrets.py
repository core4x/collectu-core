import unittest

# Internal imports.
import config
import utils.secrets


class TestSecrets(unittest.TestCase):
    """
    Recognising a credential the hub removed before publishing a configuration.

    A configuration downloaded from the hub carries `config.SECRET_PLACEHOLDER` wherever a
    parameter its module declared `secret=True` used to hold a value. The credential is simply
    not there, so the configuration loader reports it rather than letting the module fail later
    with an authentication problem.

    Nothing in this app redacts: it holds the plaintext values, serves them to its own editor
    and reports them to its motherships. Only the incoming direction needs a helper.
    """

    def test_the_placeholder_of_the_hub_is_found(self):
        configuration = [{"id": "abc", "module_name": "outputs.databases.test_1",
                          "host": "10.0.0.1", "password": config.SECRET_PLACEHOLDER}]

        self.assertEqual(utils.secrets.placeholders(configuration), [("abc", "password")])

    def test_the_placeholder_is_found_in_a_module_this_app_does_not_have(self):
        """
        Matched on the value alone: the marker is only ever written by the hub over a value it
        removed, so it means the credential is missing whether or not the module is known here.
        """
        configuration = [{"id": "abc", "module_name": "outputs.databases.does_not_exist_1",
                          "api_key": config.SECRET_PLACEHOLDER}]

        self.assertEqual(utils.secrets.placeholders(configuration), [("abc", "api_key")])

    def test_an_ordinary_configuration_holds_no_placeholder(self):
        configuration = [{"id": "abc", "module_name": "outputs.databases.test_1",
                          "password": "hunter2"}]

        self.assertEqual(utils.secrets.placeholders(configuration), [])

    def test_an_empty_configuration_is_handled(self):
        for configuration in [None, [], [{}], ["not a module"]]:
            with self.subTest(configuration=configuration):
                self.assertEqual(utils.secrets.placeholders(configuration), [])


if __name__ == '__main__':
    unittest.main()
