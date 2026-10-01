"""
Updating the app from its git repository (utils.updater).

The tests run against real repositories in a directory of their own: an upstream repository the app was cloned from,
and the installation itself, from whose src folder the app runs. The git configuration of the machine is not read, so
neither its identity nor its signing settings play a part.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

# Internal imports.
import config
import data_layer
import utils.updater
from test.helpers import GlobalStateTestCase


def _git(directory: str, *arguments: str) -> str:
    """
    Run git in a directory.

    :returns: What git printed.
    """
    return subprocess.run(["git", *arguments], cwd=directory, check=True, capture_output=True,
                          text=True).stdout.strip()


def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as file:
        return file.read()


class TestFiles(GlobalStateTestCase):
    """
    The file helpers of the updater.
    """

    def setUp(self):
        super().setUp()
        self.root = self.enter_app_directory()

    def test_a_folder_which_exists_and_is_empty(self):
        empty = os.path.join(self.root, "src", "interface")
        os.makedirs(empty)
        self.assertTrue(utils.updater.folder_exists_and_empty(empty))
        _write(os.path.join(empty, "app.py"), "")
        self.assertFalse(utils.updater.folder_exists_and_empty(empty))
        self.assertFalse(utils.updater.folder_exists_and_empty(os.path.join(self.root, "missing")))
        self.assertFalse(utils.updater.folder_exists_and_empty(os.path.join(empty, "app.py")))

    def test_a_file_is_found_by_the_beginning_of_its_name(self):
        _write(os.path.join(self.root, "git_access_token.txt"), "key")
        found = utils.updater.find_file_by_filename("git_access_token")
        self.assertEqual(os.path.normcase(found),
                         os.path.normcase(os.path.join(self.root, "git_access_token.txt").replace("\\", "/")))
        self.assertIsNone(utils.updater.find_file_by_filename("api_access_token"))


@unittest.skipIf(shutil.which("git") is None or utils.updater.git is None, "git or GitPython is not installed.")
class _RepositoryTestCase(GlobalStateTestCase):
    """
    An installation cloned from an upstream repository, with the working directory in its src folder.
    """

    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.base = os.path.realpath(directory.name)

        # Neither the identity nor the signing settings of the machine.
        empty_configuration = os.path.join(self.base, "gitconfig")
        _write(empty_configuration, "")
        os.environ.update({"GIT_CONFIG_GLOBAL": empty_configuration, "GIT_CONFIG_NOSYSTEM": "1",
                           "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@collectu.de",
                           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@collectu.de"})
        os.environ.pop("GIT_SSH_COMMAND", None)

        self.upstream = os.path.join(self.base, "upstream")
        os.makedirs(self.upstream)
        _git(self.upstream, "init", "--initial-branch=main")
        _write(os.path.join(self.upstream, "src", "main.py"), "# Version 1.\n")
        _write(os.path.join(self.upstream, "README.md"), "Collectu\n")
        # As in the repository of the app: the token files, the settings and the configurations are the
        # installation's own, which the update stashes nothing of.
        _write(os.path.join(self.upstream, ".gitignore"),
               "git_access_token.txt\napi_access_token.txt\nsettings.ini\nconfiguration/*\n")
        self.commit(self.upstream, "First commit.")
        # Annotated, as the release workflow tags: 'git describe' ignores lightweight tags.
        _git(self.upstream, "tag", "--annotate", "v1.0.0", "--message", "v1.0.0")
        self.prepare_upstream()

        self.installation = os.path.join(self.base, "installation")
        _git(self.base, "clone", "--quiet", self.upstream, self.installation)

        previous = os.getcwd()
        os.chdir(os.path.join(self.installation, "src"))
        self.addCleanup(os.chdir, previous)

        patcher = mock.patch.object(utils.updater, "restart_application")
        self.restart = patcher.start()
        self.addCleanup(patcher.stop)

    def prepare_upstream(self):
        """
        Called before the installation is cloned from the upstream repository.
        """

    @staticmethod
    def commit(repository: str, message: str):
        _git(repository, "add", "--all")
        _git(repository, "commit", "--quiet", "--message", message)

    def change_upstream(self, content: str = "# Version 2.\n", message: str = "Second commit."):
        _write(os.path.join(self.upstream, "src", "main.py"), content)
        self.commit(self.upstream, message)


class TestVersion(_RepositoryTestCase):
    """
    The version of the app is the release tag it is on, and how far it is past it.
    """

    def test_the_version_is_the_release_tag(self):
        commit = _git(self.installation, "rev-parse", "--short=7", "HEAD")
        self.assertEqual(utils.updater.determine_version(), f"v1.0.0-0-g{commit}")
        self.assertEqual(data_layer.version, f"v1.0.0-0-g{commit}")

    def test_commits_past_the_release_are_counted(self):
        _write(os.path.join(self.installation, "src", "main.py"), "# Local.\n")
        self.commit(self.installation, "A local commit.")
        self.assertTrue(utils.updater.determine_version().startswith("v1.0.0-1-g"))

    def test_without_a_repository_the_version_is_unknown(self):
        self.enter_app_directory()
        with self.assertLogs(utils.updater.logger, level="WARNING"):
            self.assertEqual(utils.updater.determine_version(), "unknown")


class TestCheckForUpdates(_RepositoryTestCase):

    def test_an_installation_on_the_latest_commit_is_up_to_date(self):
        with self.assertLogs(utils.updater.logger, level="INFO"):
            self.assertEqual(utils.updater.check_for_updates(with_submodule=False), 0)

    def test_the_commits_upstream_are_counted(self):
        self.change_upstream()
        self.change_upstream("# Version 3.\n", "Third commit.")
        with self.assertLogs(utils.updater.logger, level="INFO"):
            self.assertEqual(utils.updater.check_for_updates(with_submodule=False), 2)
        self.assertTrue(data_layer.version.startswith("v1.0.0-0-g"), "The version is determined on the way.")

    def test_without_a_repository_nothing_can_be_checked(self):
        self.enter_app_directory()
        with self.assertLogs(utils.updater.logger, level="ERROR") as logs:
            self.assertEqual(utils.updater.check_for_updates(), 0)
        self.assertIn("Update check failed", logs.output[-1])


class TestGitAccessToken(_RepositoryTestCase):
    """
    The git access token is the ssh key the private submodule is cloned with.
    """

    def test_without_a_token_the_submodule_can_not_be_updated(self):
        with self.assertLogs(utils.updater.logger, level="ERROR"):
            self.assertFalse(utils.updater.check_git_access_token())

    def test_a_token_is_used_as_the_ssh_key_of_git(self):
        token = os.path.join(self.installation, "git_access_token.txt")
        _write(token, "-----BEGIN OPENSSH PRIVATE KEY-----\n")

        self.assertTrue(utils.updater.check_git_access_token())

        command = os.environ["GIT_SSH_COMMAND"]
        self.assertIn('-i "{0}"'.format(token.replace("\\", "/")), command)
        self.assertIn("-o IdentitiesOnly=yes", command)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(os.stat(token).st_mode), 0o600)

    def test_without_a_repository_there_is_nothing_to_update(self):
        self.enter_app_directory()
        with self.assertLogs(utils.updater.logger, level="ERROR") as logs:
            self.assertFalse(utils.updater.check_git_access_token())
        self.assertIn("No git repository found", logs.output[0])


class TestUpdateApp(_RepositoryTestCase):
    """
    An update makes the installation the latest commit upstream - and puts the local changes back on top, where it
    can.
    """

    def _update(self) -> str:
        with self.assertLogs(utils.updater.logger, level="INFO"):
            return utils.updater.update_app()

    def _stashes(self) -> list[str]:
        return _git(self.installation, "stash", "list").splitlines()

    def test_an_installation_which_is_up_to_date_is_left_alone(self):
        self.assertEqual(self._update(), f"{config.APP_NAME} is already up-to-date.")
        self.restart.assert_not_called()

    def test_the_installation_is_updated_and_restarted(self):
        self.change_upstream()

        self.assertEqual(self._update(), "Successfully updated. 1 new commit(s) applied.")

        self.assertEqual(_read(os.path.join(self.installation, "src", "main.py")), "# Version 2.\n")
        self.assertEqual(_git(self.installation, "rev-parse", "HEAD"), _git(self.upstream, "rev-parse", "HEAD"))
        self.restart.assert_called_once_with()

    def test_local_changes_are_put_back(self):
        self.change_upstream()
        _write(os.path.join(self.installation, "README.md"), "Collectu, as configured here.\n")
        _write(os.path.join(self.installation, "notes.txt"), "Not part of the repository.\n")
        _write(os.path.join(self.installation, "configuration", "press.yml"), "[]\n")

        self._update()

        self.assertEqual(_read(os.path.join(self.installation, "src", "main.py")), "# Version 2.\n")
        self.assertEqual(_read(os.path.join(self.installation, "README.md")), "Collectu, as configured here.\n")
        self.assertEqual(_read(os.path.join(self.installation, "notes.txt")), "Not part of the repository.\n")
        self.assertEqual(_read(os.path.join(self.installation, "configuration", "press.yml")), "[]\n")
        self.assertEqual(self._stashes(), [])

    def test_local_changes_which_conflict_stay_stashed(self):
        self.change_upstream()
        _write(os.path.join(self.installation, "src", "main.py"), "# Changed here.\n")

        with self.assertLogs(utils.updater.logger, level="WARNING") as logs:
            utils.updater.update_app()

        self.assertIn("They remain stashed.", "\n".join(logs.output))
        self.assertEqual(len(self._stashes()), 1)
        self.assertIn("auto-update", self._stashes()[0])

    def test_a_stash_of_the_user_is_left_alone(self):
        """
        On a clean working tree nothing is stashed - and the stash popped afterwards used to be one the user had
        made by hand, which applied unrelated changes on top of the update.
        """
        _write(os.path.join(self.installation, "README.md"), "Work in progress.\n")
        _git(self.installation, "stash", "push", "--message", "the user's own")
        self.change_upstream()

        self._update()

        self.assertEqual(len(self._stashes()), 1)
        self.assertIn("the user's own", self._stashes()[0])
        self.assertEqual(_read(os.path.join(self.installation, "README.md")), "Collectu\n")

    def test_without_git_nothing_is_updated(self):
        with mock.patch.object(utils.updater, "git", None):
            self.assertIn("Git library is not available", utils.updater.update_app())
        self.restart.assert_not_called()


class TestInterfaceSubmodule(_RepositoryTestCase):
    """
    The api and the user interface are a private submodule in src/interface, which is cloned and updated with the git
    access token.
    """

    def prepare_upstream(self):
        # A submodule on the local disk, which git only clones when told to allow it.
        os.environ.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "protocol.file.allow",
                           "GIT_CONFIG_VALUE_0": "always"})
        self.interface = os.path.join(self.base, "interface")
        os.makedirs(self.interface)
        _git(self.interface, "init", "--initial-branch=main")
        _write(os.path.join(self.interface, "app.py"), "# Interface 1.\n")
        self.commit(self.interface, "First interface commit.")
        _git(self.upstream, "submodule", "--quiet", "add", self.interface, "src/interface")
        self.commit(self.upstream, "Added the interface.")

    def _token(self):
        _write(os.path.join(self.installation, "git_access_token.txt"), "-----BEGIN OPENSSH PRIVATE KEY-----\n")

    def test_an_empty_interface_folder_is_cloned_with_the_token(self):
        interface = os.path.join(self.installation, "src", "interface")
        self.assertTrue(utils.updater.folder_exists_and_empty(interface), "The clone did not leave it empty.")
        self._token()

        with self.assertLogs(utils.updater.logger, level="INFO") as logs:
            utils.updater.check_for_updates()

        self.assertEqual(_read(os.path.join(interface, "app.py")), "# Interface 1.\n")
        self.assertIn("Empty interface folder detected", "\n".join(logs.output))
        self.restart.assert_called_once_with()

    def test_without_a_token_the_interface_folder_stays_empty(self):
        with self.assertLogs(utils.updater.logger, level="ERROR"):
            utils.updater.check_for_updates()
        self.assertTrue(utils.updater.folder_exists_and_empty(os.path.join(self.installation, "src", "interface")))
        self.restart.assert_not_called()

    def test_the_interface_is_updated_with_the_app(self):
        _git(self.installation, "submodule", "--quiet", "update", "--init")
        self._token()
        _write(os.path.join(self.interface, "app.py"), "# Interface 2.\n")
        self.commit(self.interface, "Second interface commit.")
        _git(os.path.join(self.upstream, "src", "interface"), "pull", "--quiet", "origin", "main")
        self.commit(self.upstream, "Updated the interface.")

        with self.assertLogs(utils.updater.logger, level="INFO") as logs:
            utils.updater.update_app()

        self.assertEqual(_read(os.path.join(self.installation, "src", "interface", "app.py")), "# Interface 2.\n")
        self.assertIn("Updating app and submodules...", "\n".join(logs.output))
        self.restart.assert_called_once_with()


class TestRestartApplication(unittest.TestCase):

    def test_the_app_replaces_itself_with_a_new_process(self):
        with mock.patch.object(utils.updater.os, "execv") as execv, \
                mock.patch.object(utils.updater.main, "exit_handler") as exit_handler, \
                mock.patch.object(sys, "argv", ["main.py", "--cold"]):
            utils.updater.restart_application()
        exit_handler.assert_called_once_with()
        execv.assert_called_once_with(sys.executable, [sys.executable, "main.py", "--cold"])


if __name__ == '__main__':
    unittest.main()
