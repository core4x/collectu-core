"""
The configuration models every module configuration derives from: their defaults, their validation, and the
environment variables they resolve.
"""
import os
import unittest
from dataclasses import dataclass, field
from unittest import mock

# Internal imports.
import models
from models.validations import ValidationError


@dataclass
class _Configuration(models.ProcessorModule):
    """
    The configuration of a module with a parameter of each kind.
    """
    host: str = field(
        metadata=dict(description="The host.",
                      required=False),
        default="localhost")
    port: int = field(
        metadata=dict(description="The port.",
                      required=False),
        default=4840)
    timeout: float = field(
        metadata=dict(description="The timeout in seconds.",
                      required=False),
        default=1.0)
    secure: bool = field(
        metadata=dict(description="Connect securely.",
                      required=False),
        default=False)
    nodes: list[str] = field(
        metadata=dict(description="The nodes.",
                      required=False),
        default_factory=list)
    topic: str = field(
        metadata=dict(description="The topic.",
                      required=False,
                      dynamic=True),
        default="${local.measurement}")


def _module(**parameters) -> _Configuration:
    return _Configuration(**{"id": "module", "module_name": "processors.test.module_1", **parameters})


class TestDefaults(unittest.TestCase):
    """
    What a module configuration holds for the parameters a configuration leaves out.
    """

    def test_a_module_needs_nothing_but_its_id_and_name(self):
        module = models.Module(id="module", module_name="inputs.test.client_1")
        self.assertEqual((module.version, module.active, module.name, module.description, module.panel,
                          module.x, module.y, module.start_priority),
                         (0, True, "", "", "panel-1", 0, 0, 0))

    def test_the_defaults_of_each_module_type(self):
        processor = models.ProcessorModule(id="processor", module_name="processors.test.module_1")
        self.assertEqual((processor.links, processor.forward_latest_data_only, processor.worker_count_per_link),
                         ([], False, 1))
        tag = models.TagModule(id="tag", module_name="inputs.test.client_1.tag")
        self.assertEqual((tag.is_tag, tag.is_field, tag.replace_existing, tag.links), (False, True, False, []))
        variable = models.VariableModule(id="variable", module_name="inputs.test.client_1.variable")
        self.assertEqual((variable.measurement, variable.links), ("test", []))
        output = models.OutputModule(id="output", module_name="outputs.test.collector_1")
        self.assertEqual((output.buffered, output.is_buffer), (False, False))

    def test_input_and_output_modules_have_no_links(self):
        """
        An input module holds what its variable and tag modules use, and an output module is where the data ends.
        """
        self.assertFalse(hasattr(models.InputModule(id="input", module_name="inputs.test.client_1"), "links"))
        self.assertFalse(hasattr(models.OutputModule(id="output", module_name="outputs.test.collector_1"), "links"))

    def test_a_list_default_is_not_shared_between_modules(self):
        first, second = _module(id="first"), _module(id="second")
        first.links.append("target")
        first.nodes.append("ns=2;i=1")
        self.assertEqual((second.links, second.nodes), ([], []))

    def test_each_module_gets_an_id_of_its_own(self):
        """
        The default id was drawn once, as the models were imported, so all modules without an id shared it and the
        configuration reported their ids as not unique.
        """
        first, second = (models.Module(module_name="inputs.test.client_1") for _ in range(2))
        self.assertNotEqual(first.id, second.id)
        self.assertRegex(first.id, "^[a-z0-9]{19}$")


class TestValidation(unittest.TestCase):
    """
    A module configuration is validated as it is created.
    """

    def test_the_panel_is_one_of_five(self):
        for panel in ("panel-1", "panel-5"):
            self.assertEqual(_module(panel=panel).panel, panel)
        with self.assertRaises(ValidationError) as raised:
            _module(panel="panel-6")
        self.assertIn("'panel'", raised.exception.args[0][0])

    def test_the_start_priority_is_not_negative(self):
        self.assertEqual(_module(start_priority=0).start_priority, 0)
        with self.assertRaises(ValidationError):
            _module(start_priority=-1)

    def test_values_are_converted_to_the_type_of_their_parameter(self):
        module = _module(port="502", timeout="1.5", nodes=[1, 2], start_priority="3", x=10.0)
        self.assertEqual((module.port, module.timeout, module.nodes, module.start_priority, module.x),
                         (502, 1.5, ["1", "2"], 3, 10))

    def test_a_value_which_can_not_be_converted_is_reported(self):
        with self.assertRaises(ValidationError) as raised:
            _module(port="five hundred")
        self.assertEqual(len(raised.exception.args[0]), 1)
        self.assertIn("Expected field port to be of type <class 'int'>", raised.exception.args[0][0])

    def test_all_errors_are_reported_at_once(self):
        with self.assertRaises(ValidationError) as raised:
            _module(port="five hundred", panel="panel-9", start_priority=-1)
        self.assertEqual(len(raised.exception.args[0]), 3)

    def test_a_missing_required_number_is_reported(self):
        @dataclass
        class Required(models.OutputModule):
            port: int = field(
                metadata=dict(description="The port.",
                              required=True),
                default=None)

        with self.assertRaises(ValidationError) as raised:
            Required(id="output", module_name="outputs.test.collector_1")
        self.assertEqual(raised.exception.args[0], ["Missing value for field port (The port.)."])

    def test_a_missing_required_text_is_reported(self):
        """
        Read as its type, a missing text became 'None', which passed the validation, and the module started with the
        host 'None'.
        """
        @dataclass
        class Required(models.InputModule):
            host: str = field(
                metadata=dict(description="The host.",
                              required=True),
                default=None)

        with self.assertRaises(ValidationError) as raised:
            Required(id="input", module_name="inputs.test.client_1")
        self.assertEqual(raised.exception.args[0], ["Missing value for field host (The host.)."])

    def test_the_module_name_is_required(self):
        with self.assertRaises(ValidationError) as raised:
            models.Module(id="module")
        self.assertEqual(raised.exception.args[0], ["Missing value for field module_name (The name of the module.)."])

    def test_an_optional_text_without_a_value_stays_none(self):
        self.assertIsNone(_module(host=None).host)

    def test_a_text_becomes_a_boolean_by_what_it_says(self):
        """
        bool() makes every text but the empty one True, 'false' included. A parameter of the module itself is
        converted as it is read, an inherited one (active) by the validation.
        """
        for text, expected in (("true", True), ("Yes", True), ("1", True), ("on", True),
                               ("false", False), ("No", False), ("0", False), ("OFF", False), ("", False)):
            with self.subTest(text=text):
                self.assertIs(_module(secure=text).secure, expected)
                self.assertIs(_module(active=text).active, expected)

    def test_a_text_which_is_no_boolean_is_reported(self):
        for parameter in ("secure", "active"):
            with self.subTest(parameter=parameter):
                with self.assertRaises(ValidationError) as raised:
                    _module(**{parameter: "maybe"})
                self.assertIn(f"Expected field {parameter} to be of type <class 'bool'>", raised.exception.args[0][0])


class TestEnvironmentVariables(unittest.TestCase):
    """
    '${env.NAME}' in a parameter is replaced by that environment variable whenever the parameter is read, which keeps
    a secret out of the configuration.
    """

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"COLLECTU_TEST_HOST": "10.0.0.1", "COLLECTU_TEST_PORT": "502"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_parameter_is_replaced_by_the_environment_variable(self):
        self.assertEqual(_module(host="${env.COLLECTU_TEST_HOST}").host, "10.0.0.1")

    def test_the_value_takes_the_type_of_the_parameter(self):
        self.assertEqual(_module(port="${env.COLLECTU_TEST_PORT}").port, 502)

    def test_a_boolean_takes_what_the_variable_says(self):
        """
        bool() made 'false' and '0' True, so a module could not be switched off with an environment variable.
        """
        for text, expected in (("false", False), ("0", False), ("true", True), ("1", True)):
            with self.subTest(text=text):
                os.environ["COLLECTU_TEST_ENABLED"] = text
                self.assertIs(_module(secure="${env.COLLECTU_TEST_ENABLED}").secure, expected)
                self.assertIs(_module(active="${env.COLLECTU_TEST_ENABLED}").active, expected)

    def test_variables_inside_a_text_are_replaced(self):
        module = _module(host="opc.tcp://${env.COLLECTU_TEST_HOST}:${env.COLLECTU_TEST_PORT}")
        self.assertEqual(module.host, "opc.tcp://10.0.0.1:502")

    def test_the_variable_is_read_whenever_the_parameter_is(self):
        module = _module(host="${env.COLLECTU_TEST_HOST}")
        os.environ["COLLECTU_TEST_HOST"] = "10.0.0.2"
        self.assertEqual(module.host, "10.0.0.2")

    def test_an_unset_variable_is_left_as_it_is(self):
        self.assertEqual(_module(host="${env.COLLECTU_TEST_UNSET}").host, "${env.COLLECTU_TEST_UNSET}")

    def test_a_reference_to_another_module_is_left_as_it_is(self):
        """
        Only environment variables are resolved here. The data of other modules is resolved by the module, with _dyn.
        """
        self.assertEqual(_module(host="${other.host}").host, "${other.host}")

    def test_a_dynamic_parameter_is_left_to_the_module(self):
        """
        Its value can depend on the data object being processed, so the module resolves it itself, with _dyn.
        """
        self.assertEqual(_module(topic="${env.COLLECTU_TEST_HOST}").topic, "${env.COLLECTU_TEST_HOST}")


if __name__ == '__main__':
    unittest.main()
