"""
Moving and resizing the cards of a running configuration on its dashboards: the running modules are changed in place,
and the configuration is saved as the startup configuration.
"""
import json
import os
import unittest
from dataclasses import dataclass, field

# Internal imports.
import data_layer
import models
from models.validations import Range
from modules.base.processors.base import AbstractProcessorModule
from test.helpers import AppTestCase, Source, instance, module_config, wait_for


class Gauge(AbstractProcessorModule):
    """
    A dashboard module: it registers itself, and declares the size of its card as the real ones do.
    """
    description = "A dashboard module of the tests."

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        dashboard: str = field(
            metadata=dict(description="The dashboard.", required=False),
            default="Default")
        width: int = field(
            metadata=dict(description="The width.", required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=6)
        height: int = field(
            metadata=dict(description="The height.", required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=4)
        dashboard_column: int = field(
            metadata=dict(description="The column of the card.", required=False,
                          validate=Range(min=0, max=11, exclusive=False)),
            default=None)
        dashboard_row: int = field(
            metadata=dict(description="The row of the card.", required=False,
                          validate=Range(min=0, exclusive=False)),
            default=None)

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.latest_data = {}
        data_layer.dashboard_modules.append(self)
        self.starts = 0

    def start(self) -> bool:
        self.starts += 1
        return super().start()

    def _run(self, data: models.Data) -> models.Data:
        return data


class OldGauge(Gauge):
    """
    A version of a dashboard module predating the height of a card, and its position.
    """

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        dashboard: str = field(
            metadata=dict(description="The dashboard.", required=False),
            default="Default")
        width: int = field(
            metadata=dict(description="The width.", required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=6)


class UserInput(Source):
    """
    A user input module: its input mask is a card, though it does not register itself - it declares its dashboard.
    """

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        dashboard: str = field(
            metadata=dict(description="The dashboard.", required=False),
            default="Default")
        width: int = field(
            metadata=dict(description="The width.", required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=4)
        height: int = field(
            metadata=dict(description="The height, 0 to fit the fields.", required=False,
                          validate=Range(min=0, max=12, exclusive=False)),
            default=0)
        dashboard_column: int = field(
            metadata=dict(description="The column of the card.", required=False,
                          validate=Range(min=0, max=11, exclusive=False)),
            default=None)
        dashboard_row: int = field(
            metadata=dict(description="The row of the card.", required=False,
                          validate=Range(min=0, exclusive=False)),
            default=None)
        # The input fields of the mask - none here. A class attribute rather than a parameter.
        fields = ()


class Panel(AbstractProcessorModule):
    """
    A module registering itself as a dashboard module, without declaring the dashboard it is on.
    """
    description = "A dashboard module of the tests without a dashboard."

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        width: int = field(
            metadata=dict(description="The width.", required=False,
                          validate=Range(min=1, max=12, exclusive=False)),
            default=6)

    def __init__(self, configuration):
        super().__init__(configuration=configuration)
        self.latest_data = {}
        data_layer.dashboard_modules.append(self)

    def _run(self, data: models.Data) -> models.Data:
        return data


PIPELINE: list[dict] = [
    module_config("source", "inputs.test.source_1.variable", links=["gauge", "old", "panel"]),
    module_config("gauge", "processors.test.gauge_1", width=8),
    module_config("old", "processors.test.old_gauge_1"),
    module_config("panel", "processors.test.panel_1"),
    module_config("mask", "inputs.general.user_input_1.variable"),
    module_config("form", "inputs.custom.form_1.variable"),
]
"""A source feeding three dashboard modules, beside two input masks: a user input, and a custom one."""

MODULES: dict[str, type] = {"processors.test.gauge_1": Gauge,
                            "processors.test.old_gauge_1": OldGauge,
                            "processors.test.panel_1": Panel,
                            "inputs.general.user_input_1.variable": UserInput,
                            "inputs.custom.form_1.variable": UserInput}
"""The modules of PIPELINE besides the ones every test has, by module name."""


class TestUpdateDashboardLayout(AppTestCase):
    """
    Configuration.update_dashboard_layout
    """

    def setUp(self):
        super().setUp()
        data_layer.registered_modules.update(MODULES)
        self.configuration = self.create_configuration()
        self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(PIPELINE)), {})
        self.assertTrue(wait_for(lambda: instance("gauge").starts == 1))
        self.file = os.path.join(self.root, "configuration", "configuration.yml")

    def saved(self) -> dict[str, dict]:
        """
        :returns: The module configurations of the startup configuration file, by id.
        """
        with open(self.file, encoding="utf-8") as file:
            content = file.read()
        return {module["id"]: module for module in self.configuration.validate_configuration_from_stream(content)[1]}

    def test_a_card_is_moved_and_resized_without_restarting_its_module(self):
        gauge = instance("gauge")

        errors = self.configuration.update_dashboard_layout(
            [{"id": "gauge", "dashboard_column": 2, "dashboard_row": 5, "width": 10, "height": 7}])

        self.assertEqual(errors, {})
        self.assertIs(instance("gauge"), gauge)
        self.assertEqual(gauge.starts, 1)
        self.assertEqual((gauge.configuration.dashboard_column, gauge.configuration.dashboard_row,
                          gauge.configuration.width, gauge.configuration.height), (2, 5, 10, 7))
        running = next(module for module in self.configuration.configuration_dict if module["id"] == "gauge")
        self.assertEqual((running["dashboard_column"], running["dashboard_row"], running["width"],
                          running["height"]), (2, 5, 10, 7))

    def test_the_layout_is_saved_as_the_startup_configuration(self):
        self.configuration.update_dashboard_layout([{"id": "gauge", "dashboard_column": 0, "dashboard_row": 3}])

        saved = self.saved()
        self.assertEqual((saved["gauge"]["dashboard_column"], saved["gauge"]["dashboard_row"]), (0, 3))
        self.assertEqual(saved["gauge"]["width"], 8, "What was not given keeps its value.")
        self.assertEqual(set(saved), {"source", "gauge", "old", "panel", "mask", "form"})

    def test_an_autosave_is_kept_of_every_layout(self):
        self.work_off_database_queue(self.configuration)
        before = len(self.configuration.config_db.search("autosave", True))

        self.configuration.update_dashboard_layout([{"id": "gauge", "dashboard_column": 0, "dashboard_row": 0}])
        self.work_off_database_queue(self.configuration)

        self.assertEqual(len(self.configuration.config_db.search("autosave", True)), before + 1)

    def test_a_position_of_none_places_the_card_by_its_priority_again(self):
        self.configuration.update_dashboard_layout([{"id": "gauge", "dashboard_column": 1, "dashboard_row": 1}])

        errors = self.configuration.update_dashboard_layout(
            [{"id": "gauge", "dashboard_column": None, "dashboard_row": None}])

        self.assertEqual(errors, {})
        self.assertIsNone(instance("gauge").configuration.dashboard_column)
        self.assertNotIn("dashboard_column", self.saved()["gauge"])

    def test_an_input_mask_is_a_card(self):
        errors = self.configuration.update_dashboard_layout([{"id": "mask", "dashboard_column": 8,
                                                              "dashboard_row": 0, "height": 3}])

        self.assertEqual(errors, {})
        self.assertEqual(instance("mask").configuration.height, 3)

    def test_a_card_is_known_by_the_dashboard_it_declares_not_by_its_name(self):
        errors = self.configuration.update_dashboard_layout([{"id": "form", "dashboard_column": 0,
                                                              "dashboard_row": 2}])

        self.assertEqual(errors, {})
        self.assertNotIn(instance("form"), data_layer.dashboard_modules)
        self.assertEqual((instance("form").configuration.dashboard_column,
                          instance("form").configuration.dashboard_row), (0, 2))

    def test_a_registered_module_is_a_card_without_declaring_its_dashboard(self):
        errors = self.configuration.update_dashboard_layout([{"id": "panel", "width": 4}])

        self.assertEqual(errors, {})
        self.assertEqual(instance("panel").configuration.width, 4)

    def test_a_module_showing_no_card_is_refused(self):
        errors = self.configuration.update_dashboard_layout([{"id": "source", "dashboard_column": 0,
                                                              "dashboard_row": 0}])

        self.assertEqual(errors, {"source": ["The module does not show a card on a dashboard."]})

    def test_an_unknown_module_is_refused(self):
        errors = self.configuration.update_dashboard_layout([{"id": "gone", "dashboard_column": 0,
                                                              "dashboard_row": 0}])

        self.assertEqual(errors, {"gone": ["There is no running module with the id 'gone'."]})

    def test_a_size_the_module_does_not_allow_is_refused(self):
        errors = self.configuration.update_dashboard_layout([{"id": "gauge", "height": 13}])

        self.assertIn("'height'", errors["gauge"][0])
        self.assertEqual(instance("gauge").configuration.height, 4)

    def test_what_a_version_of_a_module_does_not_declare_is_refused(self):
        for key, value in (("height", 3), ("dashboard_column", 0), ("dashboard_row", 0)):
            with self.subTest(key=key):
                errors = self.configuration.update_dashboard_layout([{"id": "old", key: value}])
                self.assertEqual(errors, {"old": ["The module does not declare '{0}'. A newer version of it may: "
                                                  "update the module to place or resize its card.".format(key)]})

    def test_an_old_version_of_a_module_is_resized_in_what_it_declares(self):
        errors = self.configuration.update_dashboard_layout([{"id": "old", "width": 4}])

        self.assertEqual(errors, {})
        self.assertEqual(instance("old").configuration.width, 4)

    def test_a_card_reaching_past_the_last_column_is_refused(self):
        errors = self.configuration.update_dashboard_layout([{"id": "gauge", "dashboard_column": 5,
                                                              "dashboard_row": 0}])

        self.assertIn("does not fit on the dashboard", errors["gauge"][0])

    def test_a_card_is_placed_by_both_its_column_and_its_row(self):
        errors = self.configuration.update_dashboard_layout([{"id": "gauge", "dashboard_column": 0}])

        self.assertIn("by both dashboard_column and dashboard_row", errors["gauge"][0])

    def test_only_the_parameters_placing_a_card_are_set(self):
        errors = self.configuration.update_dashboard_layout([{"id": "gauge", "dashboard": "Line 2"}])

        self.assertEqual(errors, {"gauge": ["'dashboard' does not place a card on a dashboard."]})

    def test_a_value_which_is_not_a_whole_number_is_refused(self):
        for value in ("3", 2.5, True):
            with self.subTest(value=value):
                errors = self.configuration.update_dashboard_layout([{"id": "gauge", "width": value}])
                self.assertIn("has to be a whole number", errors["gauge"][0])

    def test_nothing_changes_if_one_card_is_refused(self):
        errors = self.configuration.update_dashboard_layout(
            [{"id": "gauge", "dashboard_column": 0, "dashboard_row": 0},
             {"id": "old", "height": 3}])

        self.assertEqual(list(errors), ["old"])
        self.assertIsNone(instance("gauge").configuration.dashboard_column)
        self.assertFalse(os.path.exists(self.file))


if __name__ == "__main__":
    unittest.main()
