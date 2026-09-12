"""
Rendering a module's docstring into the payload `GET /modules/` returns.
"""
import sys
import types
import unittest

# Internal imports.
import utils.plugin_interface

try:
    import markdown
except ImportError:
    markdown = None

DOCSTRING = """
Sign of life module.

| Key | Default |
|---|---|
| interval | 60 |

```json
{"fields": {"status": 1}}
```
"""


def module_class(name: str, docstring: str | None):
    """
    Builds a throwaway module with the given docstring and a class defined "in" it.

    `get_all_modules` reads the docstring off `sys.modules[cls.__module__]`, so the test
    has to register a real module object rather than pass a string.
    """
    module = types.ModuleType(name)
    module.__doc__ = docstring
    sys.modules[name] = module
    return type("Module", (), {"__module__": name})


class TestUtilsPluginInterface(unittest.TestCase):
    """
    This is the test for utils.plugin_interface.
    """

    def tearDown(self):
        """
        This method is called after each test.
        """
        for name in ("collectu_test_documented", "collectu_test_bare"):
            sys.modules.pop(name, None)

    def test_module_docstring_returns_the_docstring(self):
        """
        A documented module gives back exactly what it wrote.
        """
        cls = module_class("collectu_test_documented", DOCSTRING)
        self.assertEqual(DOCSTRING, utils.plugin_interface.module_docstring(cls),
                         "The docstring was not returned unchanged.")

    def test_module_docstring_returns_empty_string_without_one(self):
        """
        The crash case: no docstring must be "", never None.
        """
        cls = module_class("collectu_test_bare", None)
        result = utils.plugin_interface.module_docstring(cls)
        self.assertEqual("", result, "A module without a docstring should give an empty string.")
        self.assertIsInstance(result, str, "The result must be a string, never None.")

    @unittest.skipIf(markdown is None, "The optional markdown package is not installed.")
    def test_tables_and_fences_are_converted(self):
        """
        The extensions are what make a module's own documentation render.
        """
        html = markdown.markdown(DOCSTRING, extensions=utils.plugin_interface.MARKDOWN_EXTENSIONS)
        self.assertIn("<table>", html, "A pipe table did not become a table.")
        self.assertIn("<th>", html, "The table lost its header cells.")
        self.assertIn('class="language-json"', html,
                      "A tagged fence did not carry its language to the client.")
        self.assertNotIn("|---|", html, "The pipe syntax survived into the output.")

    @unittest.skipIf(markdown is None, "The optional markdown package is not installed.")
    def test_rendering_an_empty_docstring_does_not_raise(self):
        """
        What `get_all_modules` does for a module with no docstring, end to end.
        """
        cls = module_class("collectu_test_bare", None)
        documentation = utils.plugin_interface.module_docstring(cls)
        html = markdown.markdown(documentation,
                                 extensions=utils.plugin_interface.MARKDOWN_EXTENSIONS)
        self.assertEqual("", html, "An empty docstring should render to nothing.")


if __name__ == "__main__":
    unittest.main()
