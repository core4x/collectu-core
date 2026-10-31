"""
The dashboard stream: the layout of every card, sent before and apart from the data of the cards.
"""
import asyncio
import json
import os
import types
import unittest

# Internal imports.
import data_layer
from test.helpers import GlobalStateTestCase

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    if not os.path.isfile(os.path.join(SRC, "interface", "api_v1", "routers", "deps.py")):
        raise ImportError("The interface submodule is not checked out.")
    import interface.api_v1.routers.v1.dashboard as dashboard

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
    values = dict(id=module_id, dashboard="Default", width=6, height=4, start_priority=0, name=module_id,
                  description="")
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

        self.assertEqual(sent, [("layout", {"modules": [{"id": "image", "dashboard": "Line 1", "width": 8,
                                                         "height": 6, "start_priority": 3, "name": "Camera",
                                                         "description": "The camera."}]})])

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


if __name__ == "__main__":
    unittest.main()
