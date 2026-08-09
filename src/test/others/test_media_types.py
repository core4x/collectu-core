import importlib.util
import mimetypes
import os
import unittest

INTERFACE_MEDIA_TYPES = os.path.join(os.path.dirname(__file__), "..", "..", "interface",
                                     "api_v1", "media_types.py")


def _load():
    """
    Imports the api's media type table without importing the api.

    `interface` is a submodule, so a checkout that has not initialised it has nothing
    to test — and `media_types.py` deliberately imports nothing but `mimetypes`, so it
    can be loaded on its own rather than dragging FastAPI in.
    """
    if not os.path.isfile(INTERFACE_MEDIA_TYPES):
        return None
    spec = importlib.util.spec_from_file_location("_interface_media_types", INTERFACE_MEDIA_TYPES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


media_types = _load()


@unittest.skipIf(media_types is None, "The interface submodule is not checked out.")
class TestMediaTypes(unittest.TestCase):
    """
    The built interface is ES modules, and a browser refuses a module script that does
    not arrive as a JavaScript type. The type comes from `mimetypes`, which reads the
    machine's own database — the Windows registry, /etc/mime.types — and that database
    is wrong often enough to have taken the interface down once already: a great many
    Windows installs have `.js` registered as `text/plain`, and the whole bundle then
    fails strict MIME checking.

    So these poison the table first and assert the registration wins. Testing it on a
    machine whose database is already correct would prove nothing.
    """

    def setUp(self):
        # Restored afterwards: this is process-global state and the other tests in the
        # suite share the process.
        self._saved = dict(mimetypes.types_map)

    def tearDown(self):
        mimetypes.types_map.clear()
        mimetypes.types_map.update(self._saved)

    def test_javascript_survives_a_windows_registry_that_says_text_plain(self):
        mimetypes.types_map[".js"] = "text/plain"
        mimetypes.types_map[".css"] = "text/plain"

        media_types.register_media_types()

        self.assertIn(mimetypes.guess_type("app.js")[0], media_types.JAVASCRIPT_TYPES)
        self.assertEqual(mimetypes.guess_type("app.css")[0], "text/css")

    def test_javascript_survives_a_machine_with_no_table_at_all(self):
        mimetypes.types_map.clear()

        media_types.register_media_types()

        self.assertIn(mimetypes.guess_type("app.js")[0], media_types.JAVASCRIPT_TYPES)
        self.assertIn(mimetypes.guess_type("app.mjs")[0], media_types.JAVASCRIPT_TYPES)

    def test_every_declared_type_is_the_one_that_is_served(self):
        mimetypes.types_map.clear()

        media_types.register_media_types()

        for extension, expected in media_types.MEDIA_TYPES.items():
            with self.subTest(extension=extension):
                self.assertEqual(mimetypes.guess_type("file" + extension)[0], expected)

    def test_the_types_a_module_script_needs_are_all_covered(self):
        # Guards the table against losing an entry rather than against the OS.
        for extension in (".js", ".mjs", ".css", ".wasm", ".html"):
            self.assertIn(extension, media_types.MEDIA_TYPES)


if __name__ == "__main__":
    unittest.main()
