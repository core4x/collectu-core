import unittest

# Internal imports.
import utils.plugin_interface

# Third-party imports.
from packaging.requirements import Requirement
from packaging.version import Version
from packaging.utils import canonicalize_name


class TestThirdPartyRequirements(unittest.TestCase):
    """
    This is the test for all third party requirements.
    """

    def setUp(self):
        """
        This method is called before each test.
        Parses ../requirements.txt and builds a mapping of canonicalized package name -> pinned version.
        If a package in requirements.txt is not pinned with '==', we store None and fail later to force pinning.
        """
        self.app_packages = {}

        with open("../requirements.txt", "r") as requirements_file:
            for raw_line in requirements_file.read().splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse requirement with packaging.Requirement to handle extras/specifiers/markers.
                try:
                    req = Requirement(line)
                except Exception:
                    # If parsing fails, try a simple '=='-split as a last resort, else fail the test setup.
                    if "==" in line:
                        pkg, ver = line.split("==", 1)
                        name = pkg.strip()
                        version = ver.strip()
                        self.app_packages[canonicalize_name(name)] = version
                        continue
                    raise

                # Evaluate environment marker: if the requirement doesn't apply to this env, skip it.
                if getattr(req, "marker", None) is not None and not req.marker.evaluate():
                    continue

                name_norm = canonicalize_name(req.name)

                # Try to extract a pinned '==' version from the specifier set.
                pinned_version = None
                for spec in req.specifier:
                    # Specifier objects expose 'operator' and 'version' attributes.
                    if spec.operator == "==":
                        pinned_version = spec.version
                        break

                # If there is no pinned '==' version we store None (test will ask you to pin).
                self.app_packages[name_norm] = pinned_version

    def tearDown(self):
        """
        This method is called after each test.
        """
        pass

    def test_third_party_package_conflicts(self):
        """
        Test if there are conflicts between module requirements and the global app requirements.
        Assumes the 'packaging' library is installed.
        """
        utils.plugin_interface.load_modules()
        list_of_module_data = utils.plugin_interface.get_plugin_requirement_status()

        for module in list_of_module_data:
            requirements = module.get("requirements", []) or []
            for requirement in requirements:
                # Parse the module requirement (handles extras, specifiers, and markers).
                try:
                    req = Requirement(requirement)
                except Exception as exc:
                    self.fail(
                        f"Malformed requirement '{requirement}' in module "
                        f"'{module.get('name', 'undefined')}': {exc}"
                    )

                # If there's an environment marker and it doesn't apply, skip this requirement.
                if getattr(req, "marker", None) is not None and not req.marker.evaluate():
                    continue

                req_name_norm = canonicalize_name(req.name)

                # If the app doesn't reference this package at all, skip.
                if req_name_norm not in self.app_packages:
                    continue

                app_pinned_version = self.app_packages[req_name_norm]

                # If the app requirement is not pinned, fail the test so CI enforces pinning.
                if app_pinned_version is None:
                    self.fail(
                        f"The app's requirement for package '{req.name}' is not pinned in requirements.txt; "
                        f"please pin it with '==<version>' so this test can compare versions."
                    )

                # If the module imposes no specifier, there is nothing to conflict on.
                if not req.specifier:
                    continue

                # Check whether the app's pinned version satisfies the module's specifier set.
                satisfies = req.specifier.contains(Version(app_pinned_version), prereleases=True)
                self.assertTrue(
                    satisfies,
                    (
                        f"The module '{module.get('name', 'undefined')}' requires '{requirement}' "
                        f"but the app declares '{req.name}=={app_pinned_version}' in requirements.txt, "
                        f"which does not satisfy the specifier '{req.specifier}'."
                    )
                )
