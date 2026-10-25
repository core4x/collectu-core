"""
This function auto-updates the app using a git repository.
This will only work, if the app was checked-out via git (and not downloaded).

An update installs the newest release whose tag is signed by a key the installed version trusts
(utils/signed_releases.py) - not whatever the branch points to. A task signature only says that the hub asked for an
update, and the connection to GitHub only says that GitHub answered: whoever could push to the repository, or answer
in GitHub's place, would otherwise be running code on every Core that updates. config.VERIFY_UPDATE_SIGNATURE switches
this off for development, and the updater then follows the branch of the checkout as it used to.
"""
import os
import sys
import logging
from dataclasses import dataclass
from pathlib import Path

# Internal imports
import config
import data_layer
import main
import utils.signed_releases

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""

# Third party imports.
try:
    import git
except Exception:
    logger.error("Git is not installed. Please install git to use the update functionality.")
    git = None


def restart_application():
    """
    Restarts the application.
    """
    logger.info("Restarting application...")
    main.exit_handler()
    os.execv(sys.executable, [sys.executable] + sys.argv)


def find_file_by_filename(searched_file: str) -> str | None:
    """
    Finds a file by name in the parent directory.

    :param searched_file: Filename prefix to search for.
    :return: Absolute path or None.
    """
    parent_dir = "../"
    for filename in os.listdir(parent_dir):
        if filename.startswith(searched_file):
            return os.path.abspath(os.path.join(parent_dir, filename)).replace("\\", "/").strip()
    return None


def folder_exists_and_empty(path: str) -> bool:
    """
    Checks if a folder exists and is empty.

    :param path: Folder path.
    :return: True if exists and empty.
    """
    p = Path(path)
    return p.is_dir() and not any(p.iterdir())


def check_git_access_token() -> bool:
    """
    Validates git repo presence and access token.

    :return: True if valid.
    """
    repo_path = Path("../.git")
    token_file = find_file_by_filename("git_access_token")

    if not repo_path.is_dir():
        logger.error("No git repository found. Clone the project to use update functionality.")
        return False

    if not token_file:
        logger.error("You do not have a valid git access token for updating submodules (frontend and api). "
                     "If you have subscribed to a licence, "
                     "you can find your git access token in your account details. "
                     "If you do not have a git access token, please subscribe to a plan or contact: "
                     "{0}.".format(config.CONTACT))
        return False

    # Apply SSH key securely.
    try:
        os.chmod(token_file, 0o600)
    except Exception as e:
        logger.error("Could not prepare SSH key from git access token. Try to run app as root. Error was: {0}"
                     .format(str(e)), exc_info=config.EXC_INFO)
        return False
    # GitHub's published host keys as the only known hosts. This used to trust any server on first use - and with
    # /dev/null as the known hosts, on every use - so whoever could answer in GitHub's place was GitHub.
    known_hosts = Path(config.GITHUB_KNOWN_HOSTS_FILE).resolve()
    if not known_hosts.is_file():
        logger.error("The known hosts of GitHub ({0}) are missing, so the interface submodule cannot be updated."
                     .format(known_hosts))
    os.environ['GIT_SSH_COMMAND'] = (
        f'ssh -i "{token_file}" '
        f'-o UserKnownHostsFile="{known_hosts.as_posix()}" '
        '-o StrictHostKeyChecking=yes '
        '-o IdentitiesOnly=yes '
        f'-o ConnectTimeout={config.GIT_SSH_CONNECT_TIMEOUT_SECONDS}'
    )
    return True


_GITHUB_SSH = "git@github.com:"
"""How the interface submodule is addressed in .gitmodules: GitHub's ssh service on port 22."""

_GITHUB_SSH_PORT_443 = "ssh://git@ssh.github.com:443/"
"""GitHub's ssh service on port 443, for networks that block port 22. The same service with the same host keys, which
security/github_known_hosts lists for it - so falling back to it trusts nobody new."""

_port_22_blocked = False
"""Whether the interface submodule was last reached on port 443 only, so this run of the app tries that first rather
than waiting for port 22 to time out on every update."""


def _update_submodules(repo, *arguments: str):
    """
    Run `git submodule update` over ssh on port 22, and again on port 443 if that fails.

    Port 443 is reached by rewriting the url of the submodule for this one command (`url.<base>.insteadOf`), which
    git hands on to the clone and the fetch it runs inside the submodule. Nothing is written to a configuration: the
    next run of the app tries port 22 again, in case it was the network of the moment rather than the site.

    :param repo: The repository of the app.
    :param arguments: The arguments after `git submodule update`.
    :raises git.exc.GitCommandError: If the update fails on both ports.
    """
    global _port_22_blocked
    ports = [443, 22] if _port_22_blocked else [22, 443]
    for port, fallback in zip(ports, [*ports[1:], None]):
        try:
            if port == 443:
                repo.git(c=f"url.{_GITHUB_SSH_PORT_443}.insteadOf={_GITHUB_SSH}").submodule("update", *arguments)
            else:
                repo.git.submodule("update", *arguments)
            _port_22_blocked = port == 443
            return
        except git.exc.GitCommandError as e:
            if fallback is None:
                raise
            logger.warning("Could not update the interface submodule from GitHub on port {0}. Trying port {1} "
                           "instead: {2}".format(port, fallback, str(e.stderr).strip()))


def determine_version(repo=None) -> str:
    """
    Determines the version of this app and stores it in the data layer.

    Touches no network. A shallow clone carries no tags and legitimately yields a commit hash rather than a tag.

    :param repo: The repository to ask. Opened from the parent directory when not given.
    :return: The version, or "unknown" if it could not be determined.
    """
    try:
        # Asked of the repo object rather than a shell, so it resolves against the repository
        # instead of the working directory, and 'v*' cannot be glob-expanded on the way.
        repo = repo if repo is not None else git.Repo("..")
        data_layer.version = repo.git.describe(
            "--abbrev=7", "--always", "--long", "--match", "v*", "main").strip()
    except Exception as e:
        logger.warning("Could not determine the app version: {0}".format(str(e)))
    return data_layer.version


@dataclass
class _Update:
    """
    What an update would install.
    """
    commits: int = 0
    """How many commits the installation is behind it."""
    target: str | None = None
    """The id of the commit to install. None when there is nothing to install."""
    refused: str | None = None
    """Why the newest release is not installed, if its signature does not hold."""


def _installed_signers(repo) -> str:
    """
    The release signers file of the commit the app runs.

    From the commit rather than the working tree, which a local change - or anything else that can write to the
    disk - could have extended, and never from the release about to be installed, which could otherwise vouch for
    itself.

    :param repo: The repository of the app.
    :return: The content of the file, or "" if the installed version has none.
    """
    try:
        return repo.git.show(f"HEAD:{config.RELEASE_SIGNERS_FILE}")
    except git.exc.GitCommandError:
        return ""


def _newest_release(repo) -> str | None:
    """
    The tag of the newest release the repository knows.

    :param repo: The repository of the app.
    :return: The tag, e.g. 'v2.3.1', or None if there is no release.
    """
    releases = [(version, tag.name) for tag in repo.tags
                if (version := utils.signed_releases.release_version(tag.name)) is not None]
    return max(releases)[1] if releases else None


def _pending_update(repo) -> _Update:
    """
    What an update would install now, from what was last fetched.

    The newest release is verified only if it is ahead of the installation. A Core that is level with it - or past
    it, as one updated from the branch before releases were signed can be - has nothing to install, and nothing to
    complain about.

    :param repo: The repository of the app.
    :return: What would be installed.
    """
    if not config.VERIFY_UPDATE_SIGNATURE:
        commits = sum(1 for _ in repo.iter_commits(f"{repo.active_branch}..origin/{repo.active_branch}"))
        return _Update(commits=commits, target=repo.commit(f"origin/{repo.active_branch}").hexsha if commits else None)

    tag = _newest_release(repo)
    if tag is None:
        return _Update()
    commits = sum(1 for _ in repo.iter_commits(f"HEAD..refs/tags/{tag}"))
    if commits == 0:
        return _Update()
    try:
        # A lightweight tag is a ref to a commit and nothing that could carry a signature.
        if repo.git.cat_file("-t", f"refs/tags/{tag}") != "tag":
            raise utils.signed_releases.UnverifiedRelease(f"The tag {tag} is not signed.")
        tag_object = repo.git.cat_file("tag", f"refs/tags/{tag}", stdout_as_string=False,
                                       strip_newline_in_stdout=False)
        target = utils.signed_releases.verify_tag(
            tag_object=tag_object, tag_name=tag,
            keys=utils.signed_releases.trusted_keys(_installed_signers(repo)))
    except utils.signed_releases.UnverifiedRelease as e:
        return _Update(commits=commits, refused=str(e))
    return _Update(commits=commits, target=target)


def _check_for_updates(with_submodule: bool = True) -> _Update:
    """
    Fetches, finds what an update would install, and clones empty submodules.

    :param with_submodule: Whether to handle submodule checks.
    :return: What an update would install.
    """
    update = _Update()
    try:
        repo = git.Repo("..")

        # A checkout without a 'main' branch should still get its update check and its submodules.
        if determine_version(repo) != "unknown":
            logger.info("The app is running on version: {0}".format(data_layer.version))

        # Update local refs. The tags with them, since a release is a tag; --force, since a tag moved upstream would
        # otherwise fail the whole fetch - and whatever it points to now has to pass the signature check anyway.
        repo.git.fetch("origin", "--tags", "--force")

        update = _pending_update(repo)
        if update.refused:
            logger.error("A newer release is available but is not installed, because its signature does not hold: "
                         "{0} Please report this to {1}.".format(update.refused, config.SECURITY_EMAIL))

        # Handle submodule. check_git_access_token() is called unconditionally because it also
        # exports GIT_SSH_COMMAND, which the submodule update in update_app depends on - it must not
        # become conditional on the interface folder happening to be empty.
        token_available = check_git_access_token()
        if token_available and with_submodule and folder_exists_and_empty("./interface"):
            logger.info("Empty interface folder detected. Trying to initialize submodule...")
            try:
                _update_submodules(repo, "--init", "--recursive")
                logger.info("Successfully cloned interface submodule. Restarting...")
                restart_application()
            except Exception as e:
                logger.error("Could not initialize interface submodule: {0}"
                             .format(str(e)), exc_info=config.EXC_INFO)
    except Exception as e:
        logger.error("Update check failed: {0}".format(str(e)), exc_info=config.EXC_INFO)
    return update


def check_for_updates(with_submodule: bool = True) -> int:
    """
    Checks for new commits and clones empty submodules.

    :param with_submodule: Whether to handle submodule checks.
    :return: Number of open commits - 0 as well if the newest release is refused, which is logged as an error.
    """
    update = _check_for_updates(with_submodule=with_submodule)
    return 0 if update.refused else update.commits


def update_app() -> str:
    """
    Pulls updates and restarts if needed.

    :return: Status message.
    """
    if not git:
        return "Git library is not available on the host system. Please install git to use the update functionality."

    update = _check_for_updates()

    if update.refused:
        return f"Update refused: {update.refused}"
    if update.target is None:
        message = f"{config.APP_NAME} is already up-to-date."
        logger.info(message)
        return message

    try:
        repo = git.Repo("..")

        # --- AUTO-UPDATER POLICY ---
        # Never merge on dirty trees. Never prompt. Remote always updates.

        # 1. Stash ALL local changes (tracked + untracked).
        # Record whether this actually created a stash. On a clean tree 'stash push' stores
        # nothing, and the unconditional 'stash pop' in step 4 then popped whatever the user
        # had stashed by hand earlier - applying unrelated changes on top of the update.
        stashes_before = len(repo.git.stash("list").splitlines())
        repo.git.stash("push", "-u", "-m", "auto-update")
        stash_created = len(repo.git.stash("list").splitlines()) > stashes_before
        # 2. Force the working tree to the commit that was verified (deterministic update). By its id rather than
        # by the tag or the branch, which a fetch in the meantime could have moved somewhere unverified.
        repo.git.reset("--hard", update.target)
        # 3. Update submodules if applicable.
        if check_git_access_token() and not folder_exists_and_empty("./interface"):
            logger.info("Updating app and submodules...")
            try:
                repo.git.submodule("sync", "--recursive")  # Update .git/config
                _update_submodules(repo, "--init", "--recursive", "--force")
            except Exception as e:
                logger.error("Could not update app submodule: {0}".format(str(e)), exc_info=config.EXC_INFO)
        else:
            logger.info("Updating app...")
        # 4. Best-effort restore local changes, but only the ones we stashed ourselves.
        if stash_created:
            try:
                repo.git.stash("pop")
            except git.exc.GitCommandError:
                # Do NOT fail updater — stash is preserved for safety.
                logger.warning("Local changes could not be reapplied automatically. They remain stashed.")

        # Refresh version info.
        check_for_updates(with_submodule=False)

        message = f"Successfully updated. {update.commits} new commit(s) applied."
        logger.info(message)
        restart_application()
        return message
    except Exception as e:
        message = f"Update failed: {e}"
        logger.error(message, exc_info=config.EXC_INFO)
        return message
