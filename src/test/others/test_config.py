"""
The constants of config.py, each of which can be set by an environment variable of the same name.
"""
import importlib
import os
import unittest
from unittest import mock

# Internal imports.
import config


class TestConfig(unittest.TestCase):
    """
    config.py is read once, on import. It is imported again here with the environment of a test, and once more with
    the original environment afterwards.
    """

    def setUp(self):
        self.addCleanup(importlib.reload, config)

    @staticmethod
    def _load(**environment: str):
        with mock.patch.dict(os.environ, environment):
            return importlib.reload(config)

    def test_flags_are_switched_on_by_true_1_and_yes(self):
        for value in ("true", "True", "1", "yes", "YES"):
            with self.subTest(value=value):
                loaded = self._load(DEBUG=value, EXC_INFO=value, VERIFY_TASK_SIGNATURE=value)
                self.assertEqual((loaded.DEBUG, loaded.EXC_INFO, loaded.VERIFY_TASK_SIGNATURE), (True, True, True))
        for value in ("false", "0", "no", "", "off"):
            with self.subTest(value=value):
                loaded = self._load(DEBUG=value, EXC_INFO=value, VERIFY_TASK_SIGNATURE=value)
                self.assertEqual((loaded.DEBUG, loaded.EXC_INFO, loaded.VERIFY_TASK_SIGNATURE), (False, False, False))

    def test_the_signature_of_tasks_is_verified_by_default(self):
        environment = {key: value for key, value in os.environ.items() if key != "VERIFY_TASK_SIGNATURE"}
        with mock.patch.dict(os.environ, environment, clear=True):
            self.assertTrue(importlib.reload(config).VERIFY_TASK_SIGNATURE)

    def test_numbers_are_read_as_numbers(self):
        loaded = self._load(STOP_LIMIT="5", TASK_MAX_AGE_HOURS="1.5", ACCESS_TOKEN_EXPIRE_HOURS="2")
        self.assertEqual((loaded.STOP_LIMIT, loaded.TASK_MAX_AGE_HOURS, loaded.ACCESS_TOKEN_EXPIRE_HOURS),
                         (5, 1.5, 2.0))

    def test_the_addresses_of_the_hub_follow_its_base_address(self):
        loaded = self._load(HUB_ADDRESS="https://hub.example.com/api/v1")
        for name, path in (("HUB_MODULES_ADDRESS", "/module"), ("HUB_CONFIGURATIONS_ADDRESS", "/configuration"),
                           ("HUB_APP_ADDRESS", "/app"), ("HUB_TASK_ADDRESS", "/task/app_id"),
                           ("HUB_TEST_TOKEN_ADDRESS", "/login/test-token"),
                           ("HUB_ROLE_EFFECTIVE_ADDRESS", "/role/effective")):
            with self.subTest(address=name):
                self.assertEqual(getattr(loaded, name), "https://hub.example.com/api/v1" + path)

    def test_an_address_can_be_set_on_its_own(self):
        loaded = self._load(HUB_ADDRESS="https://hub.example.com/api/v1",
                            HUB_TASK_ADDRESS="https://tasks.example.com/task/app_id")
        self.assertEqual(loaded.HUB_TASK_ADDRESS, "https://tasks.example.com/task/app_id")
        self.assertEqual(loaded.HUB_APP_ADDRESS, "https://hub.example.com/api/v1/app")

    def test_the_security_policy_is_published_on_the_website(self):
        loaded = self._load(WEBSITE_ADDRESS="https://example.com")
        self.assertEqual(loaded.SECURITY_POLICY_URL, "https://example.com/.well-known/security-policy")


if __name__ == '__main__':
    unittest.main()
