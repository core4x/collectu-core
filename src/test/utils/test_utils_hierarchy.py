import unittest
import os

# Internal imports.
import utils.hierarchy


class HierarchyTestCase(unittest.TestCase):
    """
    Base class that gives each test a clean set of hierarchy environment variables.

    Every level is read from the environment, and the process running the tests has its own -
    a developer machine with an `APP_DESCRIPTION` set would otherwise change what these
    assert.
    """

    VARIABLES = [level.variable for level in utils.hierarchy.LEVELS] + [
        "HUB_USERNAME", "ISA95_PATH"]

    def setUp(self):
        self._saved = {name: os.environ.get(name) for name in self.VARIABLES}
        for name in self.VARIABLES:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class TestHierarchyPath(HierarchyTestCase):
    """
    Assembling the ISA-95 path an app publishes under.
    """

    def test_an_app_that_knows_nothing_about_keeps_the_path_it_always_had(self):
        """
        The whole reason empty levels are omitted rather than filled with a placeholder:
        this is the topic every existing deployment is already publishing to, and adding
        the hierarchy was not allowed to move it.
        """
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.path(), "acme/ap-xrf02")

    def test_every_level_that_is_set_appears_top_down(self):
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["SITE"] = "Stuttgart"
        os.environ["AREA"] = "Assembly"
        os.environ["WORK_CENTER"] = "Line 1"
        os.environ["WORK_UNIT"] = "Press 3"
        os.environ["EQUIPMENT_MODULE"] = "Hydraulics"
        os.environ["APP_DESCRIPTION"] = "Pressure Sensor"

        self.assertEqual(utils.hierarchy.path(),
                         "acme/Stuttgart/Assembly/Line 1/Press 3/Hydraulics/Pressure Sensor")

    def test_a_level_left_out_in_the_middle_is_skipped(self):
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["SITE"] = "Stuttgart"
        os.environ["WORK_UNIT"] = "Press 3"
        os.environ["APP_DESCRIPTION"] = "Pressure Sensor"

        self.assertEqual(utils.hierarchy.path(), "acme/Stuttgart/Press 3/Pressure Sensor")

    def test_the_enterprise_can_be_set_explicitly_for_an_app_without_a_hub_account(self):
        os.environ["ENTERPRISE"] = "acme"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.path(), "acme/ap-xrf02")

    def test_an_explicit_enterprise_wins_over_the_hub_account(self):
        os.environ["ENTERPRISE"] = "acme-gmbh"
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.path(), "acme-gmbh/ap-xrf02")

    def test_there_is_no_path_without_an_enterprise(self):
        """
        The enterprise is the root, and on the managed broker it is also the only part of a
        topic the access control cares about. A path starting at the site would be rejected
        there, so it is better not to produce one at all.
        """
        os.environ["SITE"] = "Stuttgart"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.path(), "")

    def test_separators_and_wildcards_inside_a_level_are_replaced(self):
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["WORK_CENTER"] = "Line 1/2"
        os.environ["WORK_UNIT"] = "Press +"
        os.environ["APP_DESCRIPTION"] = "#1"

        self.assertEqual(utils.hierarchy.path(), "acme/Line 1-2/Press -/-1")

    def test_surrounding_whitespace_is_not_part_of_a_level(self):
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["SITE"] = "  Stuttgart  "
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.path(), "acme/Stuttgart/ap-xrf02")

    def test_a_level_holding_only_whitespace_counts_as_unset(self):
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["SITE"] = "   "
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.path(), "acme/ap-xrf02")


class TestRefresh(HierarchyTestCase):
    """
    Publishing the assembled path back into the environment.
    """

    def test_the_path_is_published_as_an_environment_variable(self):
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.refresh(), "acme/ap-xrf02")
        self.assertEqual(os.environ.get("ISA95_PATH"), "acme/ap-xrf02")

    def test_the_variable_is_removed_rather_than_emptied_when_there_is_no_path(self):
        """
        `${env.PATH}` then fails with "could not find key", which is the same thing
        `${env.HUB_USERNAME}` has always done on an app that is not signed in - rather than
        resolving to a topic that starts with a slash and is silently rejected by the broker.
        """
        os.environ["ISA95_PATH"] = "stale/value"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"

        self.assertEqual(utils.hierarchy.refresh(), "")
        self.assertNotIn("ISA95_PATH", os.environ)

    def test_the_path_follows_a_level_that_changes(self):
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"
        utils.hierarchy.refresh()

        os.environ["SITE"] = "Stuttgart"

        self.assertEqual(utils.hierarchy.refresh(), "acme/Stuttgart/ap-xrf02")
        self.assertEqual(os.environ.get("ISA95_PATH"), "acme/Stuttgart/ap-xrf02")


class TestReported(HierarchyTestCase):
    """
    What a mothership is told about the hierarchy.
    """

    def test_only_the_middle_levels_are_reported(self):
        """
        The enterprise is the account the report authenticates as and the control module is
        the description, which is already part of every report. An app that could name its
        own enterprise would be able to file itself under somebody else's.
        """
        os.environ["HUB_USERNAME"] = "acme"
        os.environ["APP_DESCRIPTION"] = "ap-xrf02"
        os.environ["SITE"] = "Stuttgart"

        self.assertEqual(utils.hierarchy.reported(),
                         {"site": "Stuttgart", "area": "", "work_center": "",
                          "work_unit": "", "equipment_module": ""})

    def test_a_cleared_level_is_reported_as_empty_rather_than_left_out(self):
        """
        The receiving side stores what it is sent, so a level that is omitted would keep its
        old value there after the operator cleared it here.
        """
        self.assertEqual(sorted(utils.hierarchy.reported()),
                         ["area", "equipment_module", "site", "work_center", "work_unit"])


if __name__ == '__main__':
    unittest.main()
