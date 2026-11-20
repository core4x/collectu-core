"""
The dashboard stream: the layout of every card, sent before and apart from the data of the cards.
"""
import asyncio
import dataclasses
import json
import os
import types
import unittest

# Internal imports.
import data_layer
from models.validations import Range
from test.configuration.test_configuration_dashboard_layout import MODULES, PIPELINE
from test.helpers import AppTestCase, GlobalStateTestCase, instance, wait_for

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "routers", "deps.py")):
        raise ImportError("The interface submodule is not checked out.")
    import interface.api_v1.routers.v1.dashboard as dashboard
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from interface.api_v1.routers.v1 import api_router

    api_available = True
except ImportError:
    # `interface` is a submodule, which CI does not check out, and FastAPI is among the submodule's requirements
    # rather than this repository's.
    api_available = False


def visualization(module_id: str, latest_data: dict | None = None, **configuration):
    """
    A registered dashboard module, as the stream reads it.

    :param module_id: The id of the module.
    :param latest_data: What the module shows, empty until its first data object.
    :param configuration: Parameters of the configuration besides the ones every dashboard module has.
    """
    values = dict(id=module_id, dashboard="Default", width=6, height=4, start_priority=0, active=True,
                  name=module_id, description="")
    values.update(configuration)
    return types.SimpleNamespace(configuration=types.SimpleNamespace(**values), latest_data=latest_data or {})


class Request:
    """
    A connection that stays open for a number of rounds of the stream.

    :param rounds: The rounds after which the client disconnects.
    :param before_round: Called with the number of the round before it runs, to change what is registered.
    """

    def __init__(self, rounds: int, before_round=None):
        self.rounds = rounds
        self.before_round = before_round
        self.round = 0

    async def is_disconnected(self) -> bool:
        if self.round >= self.rounds:
            return True
        if self.before_round is not None:
            self.before_round(self.round)
        self.round += 1
        return False


def records(request: Request) -> list[tuple[str, dict]]:
    """
    Everything the stream sends until the client disconnects.

    :returns: The event name and the parsed payload of each record, in order.
    """

    async def collect():
        return [record async for record in dashboard.dashboard_stream_generator(request)]

    parsed = []
    for record in asyncio.run(collect()):
        lines = record.strip().split("\n")
        event = lines[0].removeprefix("event: ")
        payload = "".join(line.removeprefix("data: ") for line in lines[1:])
        parsed.append((event, json.loads(payload)))
    return parsed


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestDashboardLayout(GlobalStateTestCase):
    """
    Every card is known to the dashboard before it has data, and a card of a module that is gone is not.
    """

    def setUp(self):
        super().setUp()
        # One round of the stream is enough to read what it sends, and the tests need several.
        self.addCleanup(setattr, dashboard, "POLL_INTERVAL_SECONDS", dashboard.POLL_INTERVAL_SECONDS)
        dashboard.POLL_INTERVAL_SECONDS = 0

    def test_a_module_without_data_is_in_the_layout(self):
        data_layer.dashboard_modules = [visualization("image", dashboard="Line 1", width=8, height=6,
                                                      start_priority=3, name="Camera", description="The camera.")]

        sent = records(Request(rounds=1))

        self.assertEqual(sent, [("layout", {"modules": [{"id": "image", "dashboard": "Line 1",
                                                         "width": 8, "height": 6, "width_limits": None,
                                                         "height_limits": None, "start_priority": 3, "active": True,
                                                         "name": "Camera", "description": "The camera."}]})])

    def test_the_layout_precedes_the_data(self):
        data_layer.dashboard_modules = [visualization("text", {"id": "text", "type": "text"})]

        sent = records(Request(rounds=1))

        self.assertEqual([event for event, _ in sent], ["layout", "data"])
        self.assertEqual(sent[1][1], {"id": "text", "type": "text"})

    def test_the_layout_is_sent_again_only_when_it_changes(self):
        image = visualization("image")
        text = visualization("text")
        data_layer.dashboard_modules = [image, text]

        def before_round(number: int):
            if number == 2:
                # The text module is removed from the configuration.
                data_layer.dashboard_modules.remove(text)

        sent = records(Request(rounds=4, before_round=before_round))

        layouts = [[module["id"] for module in payload["modules"]] for event, payload in sent if event == "layout"]
        self.assertEqual(layouts, [["image", "text"], ["image"]])

    def test_an_empty_dashboard_still_gets_a_layout(self):
        # So the cards of a configuration that had dashboard modules are dropped by a dashboard still showing them.
        self.assertEqual(records(Request(rounds=1)), [("layout", {"modules": []})])

    def test_a_module_without_a_height_is_laid_out_without_one(self):
        module = visualization("old")
        del module.configuration.height

        modules = dashboard.dashboard_layout([module])["modules"]

        self.assertIsNone(modules[0]["height"])

    def test_a_card_placed_by_the_user_is_laid_out_where_it_was_placed(self):
        modules = dashboard.dashboard_layout([visualization("text", dashboard_column=6, dashboard_row=2),
                                              visualization("free", dashboard_column=None, dashboard_row=None)])
        placed = {module["id"]: (module["dashboard_column"], module["dashboard_row"]) for module in modules["modules"]}

        self.assertEqual(placed, {"text": (6, 2), "free": (None, None)})

    def test_a_version_of_a_module_which_cannot_be_placed_says_so_by_sending_no_position(self):
        # It predates the position: the dashboard places its card by its priority, and offers no way to move it.
        modules = dashboard.dashboard_layout([visualization("old")])["modules"]

        self.assertNotIn("dashboard_column", modules[0])
        self.assertNotIn("dashboard_row", modules[0])

    def test_a_card_may_be_resized_as_far_as_its_module_allows(self):
        @dataclasses.dataclass
        class Configuration:
            id: str = "chart"
            width: int = dataclasses.field(default=6, metadata=dict(validate=Range(min=1, max=12, exclusive=False)))
            height: int = dataclasses.field(default=4, metadata=dict(validate=Range(min=0, max=13)))
            start_priority: int = 0
            active: bool = True
            name: str = ""
            description: str = ""

        modules = dashboard.dashboard_layout([types.SimpleNamespace(configuration=Configuration())])["modules"]

        self.assertEqual((modules[0]["width_limits"], modules[0]["height_limits"]), ([1, 12], [1, 12]))

    def test_a_card_without_a_range_has_no_limits(self):
        @dataclasses.dataclass
        class Configuration:
            id: str = "chart"
            width: int = 6

        self.assertEqual(dashboard.size_limits(Configuration(), "width"), None)
        self.assertEqual(dashboard.size_limits(Configuration(), "height"), None)

    def test_an_inactive_module_is_laid_out_as_inactive(self):
        # Registered all the same, but it never runs: the dashboard must not wait for its data.
        modules = dashboard.dashboard_layout([visualization("on"), visualization("off", active=False)])["modules"]

        self.assertEqual([(module["id"], module["active"]) for module in modules], [("on", True), ("off", False)])


@unittest.skipUnless(api_available, "The interface submodule or FastAPI is not available.")
class TestUpdateLayout(AppTestCase):
    """
    PUT /dashboard/layout: cards are moved and resized, and the layout is saved.
    """

    def setUp(self):
        super().setUp()
        os.environ["API_AUTHENTICATION"] = "0"
        data_layer.registered_modules.update(MODULES)
        self.configuration = self.create_configuration()
        self.assertEqual(self.configuration.load_configuration_from_stream(json.dumps(PIPELINE)), {})
        self.assertTrue(wait_for(lambda: instance("gauge").starts == 1))
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        self.client = TestClient(app, base_url="https://testserver")

    def test_the_cards_are_moved_and_the_stream_follows(self):
        response = self.client.put("/api/v1/dashboard/layout", json={"cards": [
            {"id": "gauge", "dashboard_column": 4, "dashboard_row": 0, "width": 8, "height": 6},
            {"id": "old", "width": 4}]})

        self.assertEqual(response.status_code, 204)
        modules = {module["id"]: module for module in dashboard.dashboard_layout(data_layer.dashboard_modules)["modules"]}
        self.assertEqual((modules["gauge"]["dashboard_column"], modules["gauge"]["height"]), (4, 6))
        self.assertEqual(modules["gauge"]["height_limits"], [1, 12])
        self.assertEqual((modules["old"]["width"], modules["old"]["height"]), (4, None))
        self.assertNotIn("dashboard_column", modules["old"])
        self.assertEqual(instance("gauge").starts, 1, "Moving a card does not restart its module.")

    def test_a_position_of_null_is_removed_while_a_parameter_left_out_is_kept(self):
        self.client.put("/api/v1/dashboard/layout", json={"cards": [
            {"id": "gauge", "dashboard_column": 4, "dashboard_row": 0, "height": 6}]})

        response = self.client.put("/api/v1/dashboard/layout", json={"cards": [
            {"id": "gauge", "dashboard_column": None, "dashboard_row": None}]})

        self.assertEqual(response.status_code, 204)
        configuration = instance("gauge").configuration
        self.assertEqual((configuration.dashboard_column, configuration.height), (None, 6))

    def test_an_input_mask_is_moved_and_lists_where_it_is(self):
        response = self.client.put("/api/v1/dashboard/layout", json={"cards": [
            {"id": "mask", "dashboard_column": 0, "dashboard_row": 4}]})

        self.assertEqual(response.status_code, 204)
        masks = self.client.get("/api/v1/user_input").json()
        self.assertEqual((masks[0]["dashboard_column"], masks[0]["dashboard_row"]), (0, 4))
        self.assertEqual(masks[0]["height_limits"], [0, 12])

    def test_a_refused_card_is_reported_under_its_module(self):
        response = self.client.put("/api/v1/dashboard/layout", json={"cards": [
            {"id": "gauge", "dashboard_column": 0, "dashboard_row": 0},
            {"id": "old", "height": 3}]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], [{"loc": ["body", "old"], "type": "value_error",
                                                      "msg": "The module does not declare 'height'. A newer version "
                                                             "of it may: update the module to place or resize its "
                                                             "card."}])
        self.assertIsNone(instance("gauge").configuration.dashboard_column)

    def test_only_whole_numbers_and_known_parameters_are_taken(self):
        for card in ({"id": "gauge", "width": "4"}, {"id": "gauge", "width": 4.5}, {"id": "gauge", "colour": "red"}):
            with self.subTest(card=card):
                response = self.client.put("/api/v1/dashboard/layout", json={"cards": [card]})
                self.assertEqual(response.status_code, 422)

    def test_some_card_has_to_be_given(self):
        self.assertEqual(self.client.put("/api/v1/dashboard/layout", json={"cards": []}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
