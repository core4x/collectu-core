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
import shlex
import sys
import logging
from dataclasses import dataclass, field
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
    # Git runs this in a shell, so every value is quoted for one. The known hosts are quoted once more, for ssh itself:
    # UserKnownHostsFile takes a list of files separated by spaces, so an installation in 'Collectu GitHub' named two
    # files that do not exist - and with strict checking, no host was known at all.
    os.environ['GIT_SSH_COMMAND'] = " ".join([
        "ssh",
        "-i", shlex.quote(str(token_file)),
        "-o", shlex.quote(f'UserKnownHostsFile="{known_hosts.as_posix()}"'),
        "-o", "StrictHostKeyChecking=yes",
        "-o", "IdentitiesOnly=yes",
        "-o", f"ConnectTimeout={config.GIT_SSH_CONNECT_TIMEOUT_SECONDS}",
    ])
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
    refused: list[str] = field(default_factory=list)
    """Why each release ahead of the installation that did not pass was passed over, oldest first. With a target, they
    were skipped; without one, nothing is installed because of them."""


def _signers(repo, revision: str) -> str:
    """
    The release signers file of a commit.

    Read from a commit - the installed one, or a release that passed the check - and never from the working tree, which
    a local change, or anything else that can write to the disk, could have extended.

    :param repo: The repository of the app.
    :param revision: The commit.
    :return: The content of the file, or "" if that version has none.
    """
    try:
        return repo.git.show(f"{revision}:{config.RELEASE_SIGNERS_FILE}")
    except git.exc.GitCommandError:
        return ""


def _releases_ahead(repo) -> list[str]:
    """
    The release tags whose commit the installation does not contain yet, oldest release first.

    Ahead by the history rather than by the number: a tag anybody can push onto an old commit, v99.0.0 say, names a
    commit the installation already has and so is no release ahead of it.

    :param repo: The repository of the app.
    :return: The tags, e.g. ['v2.3.1', 'v2.4.0'].
    """
    releases = []
    for tag in repo.git.tag("--list", "v*", "--no-merged", "HEAD").split():
        version = utils.signed_releases.release_version(tag)
        if version is not None:
            releases.append((version, tag))
    return [tag for _, tag in sorted(releases)]


def _verified_release(repo, tag: str, keys: list[bytes]) -> str:
    """
    Verify one release tag.

    :param repo: The repository of the app.
    :param tag: The tag.
    :param keys: The keys it may be signed with.
    :return: The id of the commit it names.
    :raises utils.signed_releases.UnverifiedRelease: If it does not pass.
    """
    # A lightweight tag is a ref to a commit and nothing that could carry a signature.
    if repo.git.cat_file("-t", f"refs/tags/{tag}") != "tag":
        raise utils.signed_releases.UnverifiedRelease(f"The tag {tag} is not signed.")
    tag_object = repo.git.cat_file("tag", f"refs/tags/{tag}", stdout_as_string=False, strip_newline_in_stdout=False)
    return utils.signed_releases.verify_tag(tag_object=tag_object, tag_name=tag, keys=keys)


def _pending_update(repo) -> _Update:
    """
    What an update would install now, from what was last fetched.

    The releases ahead of the installation are walked through oldest first, with trust carried along: each is checked
    against the signers file of the last one that passed - the installed version's, to begin with - and one that
    passes hands its own file on to the next. The newest that passes is installed.

    So a Core that missed the release which added a new key still gets there, by way of it, and nobody has to wait for
    the whole fleet before switching to that key. And a Core that passes the release revoking a key stops trusting it
    from there on, within the same update - a release signed with that key after its revocation is refused even by a
    Core that has never installed the revocation. Taking the newest release that verifies against the installed keys
    alone would install exactly that one.

    A release that fails is passed over rather than ending the walk. Otherwise one tag that anybody with push access can
    create - an unsigned v99.0.0 on a new commit - would hold every Core on its version for good: a Core keeps the tags
    it has fetched, even once they are deleted upstream.

    A Core that is level with the newest release - or past it, as one updated from the branch before releases were
    signed can be - has nothing ahead of it, and nothing to complain about.

    :param repo: The repository of the app.
    :return: What would be installed.
    """
    if not config.VERIFY_UPDATE_SIGNATURE:
        commits = sum(1 for _ in repo.iter_commits(f"{repo.active_branch}..origin/{repo.active_branch}"))
        return _Update(commits=commits, target=repo.commit(f"origin/{repo.active_branch}").hexsha if commits else None)

    keys = utils.signed_releases.trusted_keys(_signers(repo, "HEAD"))
    target, refused = None, []
    for tag in _releases_ahead(repo):
        try:
            commit = _verified_release(repo, tag, keys)
        except utils.signed_releases.UnverifiedRelease as e:
            refused.append(str(e))
            continue
        target = commit
        keys = utils.signed_releases.trusted_keys(_signers(repo, commit))
    if target is None:
        return _Update(refused=refused)
    return _Update(commits=sum(1 for _ in repo.iter_commits(f"HEAD..{target}")), target=target, refused=refused)


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
        # Logged as errors either way: a release tag that does not hold is either a broken release or somebody
        # trying to get code onto this Core.
        for reason in update.refused:
            if update.target:
                logger.error("A newer release is skipped, because its signature does not hold: {0} The newest release "
                             "that holds is installed instead. Please report this to {1}."
                             .format(reason, config.SECURITY_EMAIL))
            else:
                logger.error("A newer release is available but is not installed, because its signature does not "
                             "hold: {0} Please report this to {1}.".format(reason, config.SECURITY_EMAIL))

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
    :return: Number of commits to the newest release that holds - 0 if none ahead does. A release that does not hold
        is logged as an error.
    """
    update = _check_for_updates(with_submodule=with_submodule)
    return update.commits if update.target else 0


def update_app() -> str:
    """
    Pulls updates and restarts if needed.

    :return: Status message.
    """
    if not git:
        return "Git library is not available on the host system. Please install git to use the update functionality."

    update = _check_for_updates()

    if update.target is None and update.refused:
        # The newest of them is the one an operator asked for.
        return f"Update refused: {update.refused[-1]}"
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
