import os
import shutil
import tempfile
import unittest

# Internal imports.
import utils.config_store


class TestStoreEquivalence(unittest.TestCase):
    """
    The two stores have to be indistinguishable to a caller.

    `config_store` exists so that `configuration.py` and `utils/mothership_interface.py`
    carry one code path instead of an `if tinydb:` at every call site. That only holds
    while the two implementations agree, and the in-memory one is the half that does
    not run in normal operation — so nothing but this would notice it drifting.

    Everything is asserted against both, side by side, rather than against recorded
    expectations: the property being tested is agreement, not a particular answer.
    """

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.stores = {
            "tinydb": utils.config_store.TinyDbStore(os.path.join(self.directory, "test.db")),
            "memory": utils.config_store.MemoryStore(),
        }

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def _both(self, call):
        """Runs `call` against each store and returns {name: result}."""
        return {name: call(store) for name, store in self.stores.items()}

    def _agree(self, call, message):
        results = self._both(call)
        self.assertEqual(results["tinydb"], results["memory"], message)
        return results["tinydb"]

    def _seed(self):
        for store in self.stores.values():
            store.insert({"id": "a", "title": "one", "autosave": True, "updated_at": "2026-01-01"})
            store.insert({"id": "b", "title": "two", "autosave": False, "updated_at": "2026-01-02"})

    def test_insert_and_all(self):
        self._seed()
        self.assertEqual(self._agree(lambda s: len(s.all()), "entry count"), 2)

    def test_get_hit_and_miss(self):
        self._seed()
        self.assertEqual(self._agree(lambda s: s.get("id", "a")["title"], "get by id"), "one")
        self.assertIsNone(self._agree(lambda s: s.get("id", "missing"), "get with no match"))

    def test_search_by_a_non_id_field(self):
        # The autosave pruning in configuration.py depends on this one.
        self._seed()
        self.assertEqual(self._agree(lambda s: len(s.search("autosave", True)), "search"), 1)
        self.assertEqual(self._agree(lambda s: s.search("autosave", False)[0]["id"], "search"), "b")

    def test_update_reports_how_many_it_changed(self):
        # The callers use this to decide between a debug and a warning line.
        self._seed()
        self.assertEqual(
            self._agree(lambda s: s.update({"title": "renamed"}, "id", "a"), "update hit"), 1
        )
        self.assertEqual(self._agree(lambda s: s.get("id", "a")["title"], "after update"), "renamed")
        self.assertEqual(
            self._agree(lambda s: s.update({"title": "x"}, "id", "missing"), "update miss"), 0
        )

    def test_remove_reports_how_many_it_removed(self):
        self._seed()
        self.assertEqual(self._agree(lambda s: s.remove("id", "b"), "remove hit"), 1)
        self.assertEqual(self._agree(lambda s: len(s.all()), "after remove"), 1)
        self.assertEqual(self._agree(lambda s: s.remove("id", "missing"), "remove miss"), 0)

    def test_iteration_yields_the_entries(self):
        # `for app in self.db` in the mothership worker relies on this.
        self._seed()
        self.assertEqual(self._agree(lambda s: sorted(e["id"] for e in s), "iteration"), ["a", "b"])

    def test_an_empty_store_is_empty_not_an_error(self):
        self.assertEqual(self._agree(lambda s: s.all(), "empty"), [])
        self.assertIsNone(self._agree(lambda s: s.get("id", "a"), "empty get"))
        self.assertEqual(self._agree(lambda s: s.search("autosave", True), "empty search"), [])

    def test_only_persistence_differs(self):
        # The one thing they are allowed to disagree about, and the thing the api
        # reports as `configuration_library_persistent`.
        self.assertTrue(self.stores["tinydb"].persistent)
        self.assertFalse(self.stores["memory"].persistent)


class TestMemoryStoreIsolation(unittest.TestCase):
    """
    The in-memory store hands out copies.

    tinydb serialises through a file, so a caller can never hold a reference into the
    store. The in-memory one has to arrange that itself, or a caller mutating a
    returned dict would edit the stored entry behind everyone's back.
    """

    def setUp(self):
        self.store = utils.config_store.MemoryStore()
        self.store.insert({"id": "a", "title": "one"})

    def test_all_returns_copies(self):
        self.store.all()[0]["title"] = "mutated"
        self.assertEqual(self.store.get("id", "a")["title"], "one")

    def test_get_returns_a_copy(self):
        entry = self.store.get("id", "a")
        entry["title"] = "mutated"
        self.assertEqual(self.store.get("id", "a")["title"], "one")

    def test_insert_copies_what_it_is_given(self):
        entry = {"id": "b", "title": "two"}
        self.store.insert(entry)
        entry["title"] = "mutated"
        self.assertEqual(self.store.get("id", "b")["title"], "two")


if __name__ == "__main__":
    unittest.main()
