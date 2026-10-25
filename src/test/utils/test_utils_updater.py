"""
Updating the app from its git repository (utils.updater).

The tests run against real repositories in a directory of their own: an upstream repository the app was cloned from,
and the installation itself, from whose src folder the app runs. The git configuration of the machine is not read, so
neither its identity nor its signing settings play a part.

Releases are signed by git itself, with a key made for each test and trusted by the first commit upstream - as the
release workflow signs them. That takes git 2.34 and ssh-keygen; without them, the tests that release are skipped.
"""
import os
import pathlib
import re
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

# Third party imports.
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    serialization = Ed25519PrivateKey = None


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


def _can_sign() -> bool:
    """
    Whether git can sign tags with ssh keys here: git 2.34 or later, ssh-keygen, and cryptography to make the key.
    """
    if shutil.which("git") is None or shutil.which("ssh-keygen") is None or Ed25519PrivateKey is None:
        return False
    version = re.search(r"(\d+)\.(\d+)", subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
    return version is not None and tuple(int(part) for part in version.groups()) >= (2, 34)


def _signing_key(path: str) -> str:
    """
    Make an ed25519 key pair for signing releases.

    :param path: Where the private key is written, readable by its owner only - ssh-keygen refuses it otherwise.
    :returns: Its line for an allowed signers file.
    """
    key = Ed25519PrivateKey.generate()
    with open(path, "wb") as file:
        file.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                     serialization.NoEncryption()))
    os.chmod(path, 0o600)
    public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
    return f'release@collectu.de namespaces="git" {public.decode()}\n'


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
        _write(os.path.join(self.upstream, "security", "github_known_hosts"), "github.com ssh-ed25519 AAAA\n")
        # The key releases are signed with, trusted from the first commit on.
        self.release_key = os.path.join(self.base, "release_key")
        self.signers = _signing_key(self.release_key) if _can_sign() else ""
        _write(os.path.join(self.upstream, "security", "allowed_signers"), self.signers)
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

    def release(self, tag: str = "v1.1.0", key: str | None = None):
        """
        Tag the newest commit upstream as a release, signed as the release workflow signs it.

        :param tag: The tag.
        :param key: The private key to sign with. The trusted one if not given.
        """
        if not _can_sign():
            self.skipTest("git 2.34, ssh-keygen and cryptography are needed to sign a release.")
        signing_key = (key or self.release_key).replace(os.sep, "/")
        _git(self.upstream, "-c", "gpg.format=ssh", "-c", f"user.signingkey={signing_key}",
             "tag", "--sign", tag, "--message", tag)


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
        self.release()
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
        # GitHub's own host keys and nothing else, rather than whichever server answers.
        known_hosts = os.path.join(self.installation, "security", "github_known_hosts").replace("\\", "/")
        self.assertIn('-o UserKnownHostsFile="{0}"'.format(known_hosts), command)
        self.assertIn("-o StrictHostKeyChecking=yes", command)
        self.assertNotIn("StrictHostKeyChecking=no", command)
        # A port a firewall drops fails within seconds rather than the minutes of the TCP timeout.
        self.assertIn(f"-o ConnectTimeout={config.GIT_SSH_CONNECT_TIMEOUT_SECONDS}", command)
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
        self.release()

        self.assertEqual(self._update(), "Successfully updated. 1 new commit(s) applied.")

        self.assertEqual(_read(os.path.join(self.installation, "src", "main.py")), "# Version 2.\n")
        self.assertEqual(_git(self.installation, "rev-parse", "HEAD"), _git(self.upstream, "rev-parse", "HEAD"))
        self.restart.assert_called_once_with()

    def test_local_changes_are_put_back(self):
        self.change_upstream()
        self.release()
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
        self.release()
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
        self.release()

        self._update()

        self.assertEqual(len(self._stashes()), 1)
        self.assertIn("the user's own", self._stashes()[0])
        self.assertEqual(_read(os.path.join(self.installation, "README.md")), "Collectu\n")

    def test_without_git_nothing_is_updated(self):
        with mock.patch.object(utils.updater, "git", None):
            self.assertIn("Git library is not available", utils.updater.update_app())
        self.restart.assert_not_called()


class TestSignedReleases(_RepositoryTestCase):
    """
    An update installs the newest release signed by a key the installed version trusts - and nothing else.
    """

    def _update(self, level: str = "INFO") -> tuple[str, str]:
        with self.assertLogs(utils.updater.logger, level=level) as logs:
            message = utils.updater.update_app()
        return message, "\n".join(logs.output)

    def _installed(self) -> str:
        return _git(self.installation, "rev-parse", "HEAD")

    def _other_key(self, name: str = "other_key") -> tuple[str, str]:
        """
        A key pair nobody trusts yet: the private key's path and its allowed signers line.
        """
        if not _can_sign():
            self.skipTest("git 2.34, ssh-keygen and cryptography are needed to sign a release.")
        path = os.path.join(self.base, name)
        return path, _signing_key(path)

    def _trust(self, *signers: str, message: str):
        """
        Commit a release signers file upstream that names exactly these keys.
        """
        _write(os.path.join(self.upstream, "security", "allowed_signers"), "".join(signers))
        self.commit(self.upstream, message)

    def _installed_signers(self) -> str:
        return _read(os.path.join(self.installation, "security", "allowed_signers"))

    def test_a_signed_release_is_installed(self):
        self.change_upstream()
        self.release("v1.1.0")

        message, _ = self._update()

        self.assertEqual(message, "Successfully updated. 1 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.1.0^{commit}"))
        self.assertTrue(data_layer.version.startswith("v1.1.0-0-g"))
        self.restart.assert_called_once_with()

    def test_what_is_past_the_newest_release_is_not_installed(self):
        self.change_upstream()
        self.release("v1.1.0")
        self.change_upstream("# Version 3, not released.\n", "Third commit.")

        self._update()

        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.1.0^{commit}"))
        self.assertEqual(_read(os.path.join(self.installation, "src", "main.py")), "# Version 2.\n")

    def test_the_newest_of_several_releases_is_installed(self):
        for minor in (1, 2, 10):
            self.change_upstream(f"# Version 1.{minor}.\n", f"Release 1.{minor}.")
            self.release(f"v1.{minor}.0")

        message, _ = self._update()

        self.assertEqual(message, "Successfully updated. 3 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.10.0^{commit}"))

    def test_an_installation_level_with_the_newest_release_has_nothing_to_install(self):
        self.change_upstream()
        self.release("v1.1.0")
        self._update()
        self.restart.reset_mock()

        message, logs = self._update()

        self.assertEqual(message, f"{config.APP_NAME} is already up-to-date.")
        self.assertNotIn("signature", logs)
        self.restart.assert_not_called()

    def _assert_refused(self, reason: str):
        installed = self._installed()
        message, logs = self._update(level="ERROR")
        self.assertTrue(message.startswith("Update refused:"), message)
        self.assertIn(reason, message)
        self.assertIn("is not installed, because its signature does not hold", logs)
        self.assertEqual(self._installed(), installed)
        self.restart.assert_not_called()
        # Nor is it offered as an update anybody could apply.
        with self.assertLogs(utils.updater.logger, level="ERROR"):
            self.assertEqual(utils.updater.check_for_updates(with_submodule=False), 0)

    def test_an_unsigned_release_is_refused(self):
        self.change_upstream()
        _git(self.upstream, "tag", "--annotate", "v1.1.0", "--message", "v1.1.0")
        self._assert_refused("The tag v1.1.0 is not signed.")

    def test_a_lightweight_tag_is_refused(self):
        self.change_upstream()
        _git(self.upstream, "tag", "v1.1.0")
        self._assert_refused("The tag v1.1.0 is not signed.")

    def test_a_release_signed_by_an_unknown_key_is_refused(self):
        other_key, _ = self._other_key()
        self.change_upstream()
        self.release("v1.1.0", key=other_key)
        self._assert_refused("signed with a key that is not in security/allowed_signers")

    def test_a_release_cannot_vouch_for_its_own_key(self):
        """
        The signers file is read from the installed version: a release that adds a key and is signed with it would
        otherwise be trusted on its own word.
        """
        other_key, other_signer = self._other_key()
        _write(os.path.join(self.upstream, "security", "allowed_signers"), self.signers + other_signer)
        self.commit(self.upstream, "Trusts another key.")
        self.release("v1.1.0", key=other_key)
        self._assert_refused("signed with a key that is not in security/allowed_signers")

    def test_a_key_added_by_a_trusted_release_signs_the_next_one(self):
        """
        Rotating the key: a release signed with the old key brings the new one, and the next release is signed with
        that.
        """
        other_key, other_signer = self._other_key()
        _write(os.path.join(self.upstream, "security", "allowed_signers"), self.signers + other_signer)
        self.commit(self.upstream, "Trusts the next key.")
        self.release("v1.1.0")
        self._update()

        self.change_upstream()
        self.release("v1.2.0", key=other_key)
        message, _ = self._update()

        self.assertEqual(message, "Successfully updated. 1 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.2.0^{commit}"))

    def test_a_core_that_missed_a_key_rotation_catches_up(self):
        """
        The whole rotation happened while this Core was not updating: it trusts the old key only, and the newest
        release is signed with the new one. It gets there by way of the release that introduced the new key.
        """
        new_key, new_signer = self._other_key("new_key")
        self._trust(self.signers, new_signer, message="Trusts the next key.")
        self.release("v1.1.0")
        self.change_upstream()
        self.release("v1.2.0", key=new_key)
        self._trust(new_signer, message="No longer trusts the old key.")
        self.release("v1.3.0", key=new_key)

        message, logs = self._update()

        self.assertEqual(message, "Successfully updated. 3 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.3.0^{commit}"))
        self.assertEqual(self._installed_signers(), new_signer)
        self.assertNotIn("signature does not hold", logs)

    def test_a_revoked_key_is_not_trusted_past_its_revocation(self):
        """
        The old key leaked after it was revoked, and whoever has it signs a release. A Core that never installed the
        revocation still trusts the old key - but it passes the revocation on the way, and stops there.
        """
        new_key, new_signer = self._other_key("new_key")
        self._trust(self.signers, new_signer, message="Trusts the next key.")
        self.release("v1.1.0")
        self._trust(new_signer, message="Revokes the old key.")
        self.release("v1.2.0", key=new_key)
        self.change_upstream("# Not by Collectu.\n", "A release with the leaked key.")
        self.release("v1.3.0")

        message, logs = self._update(level="ERROR")

        self.assertEqual(message, "Successfully updated. 2 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.2.0^{commit}"))
        self.assertIn("A newer release is skipped, because its signature does not hold: The tag v1.3.0 is signed "
                      "with a key that is not in security/allowed_signers.", logs)

    def test_a_core_past_the_revocation_refuses_the_revoked_key(self):
        new_key, new_signer = self._other_key("new_key")
        self._trust(new_signer, message="Revokes the old key.")
        self.release("v1.1.0")
        self._update()
        self.restart.reset_mock()

        self.change_upstream("# Not by Collectu.\n", "A release with the leaked key.")
        self.release("v1.2.0")

        self._assert_refused("The tag v1.2.0 is signed with a key that is not in security/allowed_signers.")

    def test_a_bogus_newest_tag_does_not_hold_back_the_newest_release(self):
        """
        Anybody who can push can create v99.0.0. Ending the walk there would keep every Core on its version for good -
        even once the tag is deleted upstream, since a Core keeps the tags it has fetched.
        """
        self.change_upstream()
        self.release("v1.1.0")
        self.change_upstream("# Not by Collectu.\n", "Unsigned.")
        _git(self.upstream, "tag", "--annotate", "v99.0.0", "--message", "v99.0.0")

        message, logs = self._update(level="ERROR")

        self.assertEqual(message, "Successfully updated. 1 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.1.0^{commit}"))
        self.assertIn("A newer release is skipped, because its signature does not hold: The tag v99.0.0 is not "
                      "signed.", logs)

    def test_a_signed_release_after_a_bogus_one_is_installed(self):
        self.change_upstream("# Not by Collectu.\n", "Unsigned.")
        _git(self.upstream, "tag", "--annotate", "v1.1.0", "--message", "v1.1.0")
        self.change_upstream()
        self.release("v1.2.0")

        message, _ = self._update(level="ERROR")

        self.assertEqual(message, "Successfully updated. 2 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "v1.2.0^{commit}"))

    def test_a_tag_on_a_commit_the_core_has_is_no_release_ahead(self):
        """
        Ahead by the history, not by the number: a v99.0.0 on an old commit neither installs nor blocks anything.
        """
        _git(self.upstream, "tag", "--annotate", "v99.0.0", "--message", "v99.0.0", "v1.0.0^{commit}")
        self.change_upstream()
        self.release("v1.1.0")

        message, logs = self._update()

        self.assertEqual(message, "Successfully updated. 1 new commit(s) applied.")
        self.assertNotIn("v99.0.0", logs)

    def test_tags_that_are_no_releases_are_ignored(self):
        self.change_upstream()
        _git(self.upstream, "tag", "--annotate", "v1.1.0-rc.1", "--message", "A release candidate.")
        _git(self.upstream, "tag", "latest")

        message, _ = self._update()

        self.assertEqual(message, f"{config.APP_NAME} is already up-to-date.")

    def test_without_verification_the_branch_is_followed(self):
        self.patch_config(VERIFY_UPDATE_SIGNATURE=False)
        self.change_upstream()

        message, _ = self._update()

        self.assertEqual(message, "Successfully updated. 1 new commit(s) applied.")
        self.assertEqual(self._installed(), _git(self.upstream, "rev-parse", "HEAD"))


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
        self.release()

        with self.assertLogs(utils.updater.logger, level="INFO") as logs:
            utils.updater.update_app()

        self.assertEqual(_read(os.path.join(self.installation, "src", "interface", "app.py")), "# Interface 2.\n")
        self.assertIn("Updating app and submodules...", "\n".join(logs.output))
        self.restart.assert_called_once_with()


class TestBlockedPort22(_RepositoryTestCase):
    """
    A network that blocks port 22 gets the interface from GitHub's ssh service on port 443.

    The two addresses are two file urls here: the one .gitmodules names, which leads nowhere - port 22, blocked - and
    the one the updater rewrites it to, which holds the interface. So what is tested is git's own rewriting, handed on
    to the clone inside the submodule, not a stand-in for it.

    Urls rather than paths, as `git@github.com:` is one. Git refuses a local path that does not exist before it
    rewrites anything - so with plain paths the tests passed on Windows, whose paths carry a colon and so read as urls,
    and failed on Linux.
    """

    def prepare_upstream(self):
        os.environ.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "protocol.file.allow",
                           "GIT_CONFIG_VALUE_0": "always"})
        self.port_22 = pathlib.Path(self.base).as_uri() + "/port22/"
        self.port_443 = pathlib.Path(self.base).as_uri() + "/port443/"
        self.nowhere = pathlib.Path(self.base).as_uri() + "/nowhere/"
        interface = os.path.join(self.base, "port443", "interface")
        os.makedirs(interface)
        _git(interface, "init", "--initial-branch=main")
        _write(os.path.join(interface, "app.py"), "# Interface 1.\n")
        self.commit(interface, "First interface commit.")
        _git(self.upstream, "submodule", "--quiet", "add", self.port_443 + "interface", "src/interface")
        _git(self.upstream, "config", "--file", ".gitmodules", "submodule.src/interface.url", self.port_22 + "interface")
        self.commit(self.upstream, "Added the interface.")

    def setUp(self):
        super().setUp()
        for name, value in (("_GITHUB_SSH", self.port_22), ("_GITHUB_SSH_PORT_443", self.port_443),
                            ("_port_22_blocked", False)):
            patcher = mock.patch.object(utils.updater, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        _write(os.path.join(self.installation, "git_access_token.txt"), "-----BEGIN OPENSSH PRIVATE KEY-----\n")
        self.interface = os.path.join(self.installation, "src", "interface")

    def _check(self) -> str:
        with self.assertLogs(utils.updater.logger, level="INFO") as logs:
            utils.updater.check_for_updates()
        return "\n".join(logs.output)

    def test_the_interface_is_cloned_on_port_443_when_port_22_fails(self):
        logs = self._check()

        self.assertEqual(_read(os.path.join(self.interface, "app.py")), "# Interface 1.\n")
        self.assertIn("on port 22. Trying port 443 instead", logs)
        self.assertTrue(utils.updater._port_22_blocked)
        self.restart.assert_called_once_with()

    def test_once_port_22_failed_port_443_is_tried_first(self):
        utils.updater._port_22_blocked = True

        logs = self._check()

        self.assertEqual(_read(os.path.join(self.interface, "app.py")), "# Interface 1.\n")
        self.assertNotIn("Trying port", logs)

    def test_port_22_is_tried_again_when_port_443_fails(self):
        """
        The network the app runs in can change - a laptop, a VPN - so a blocked port 22 is not assumed for good.
        """
        utils.updater._port_22_blocked = True
        # Port 22 works this time: .gitmodules points at the interface itself - and port 443 is rewritten to nowhere.
        _git(self.installation, "config", "--file", ".gitmodules", "submodule.src/interface.url",
             self.port_443 + "interface")
        utils.updater._GITHUB_SSH = self.port_443
        utils.updater._GITHUB_SSH_PORT_443 = self.nowhere

        logs = self._check()

        self.assertEqual(_read(os.path.join(self.interface, "app.py")), "# Interface 1.\n")
        self.assertIn("on port 443. Trying port 22 instead", logs)
        self.assertFalse(utils.updater._port_22_blocked)

    def test_the_interface_stays_empty_when_neither_port_works(self):
        utils.updater._GITHUB_SSH_PORT_443 = self.nowhere

        logs = self._check()

        self.assertTrue(utils.updater.folder_exists_and_empty(self.interface))
        self.assertIn("Could not initialize interface submodule", logs)
        self.restart.assert_not_called()


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
