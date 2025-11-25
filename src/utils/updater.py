"""
This function auto-updates the app using a git repository.
This will only work, if the app was checked-out via git (and not downloaded).
"""
import os
import sys
import logging
import subprocess
from pathlib import Path

# Internal imports
import config
import data_layer
import main

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
    os.chmod(token_file, 0o600)
    os.environ['GIT_SSH_COMMAND'] = (
        f'ssh -i "{token_file}" '
        '-o UserKnownHostsFile=/dev/null '
        '-o StrictHostKeyChecking=no '
        '-o IdentitiesOnly=yes'
    )
    return True


def check_for_updates(with_submodule: bool = True) -> int:
    """
    Checks for new commits and clones empty submodules.

    :param with_submodule: Whether to handle submodule checks.
    :return: Number of open commits.
    """
    commit_count = 0

    try:
        repo = git.Repo("..")

        # Get version info.
        result = subprocess.run("git describe --abbrev=7 --always --long --match v* main",
                                stdout=subprocess.PIPE, shell=True, universal_newlines=True)
        data_layer.version = result.stdout.strip()

        # Update local refs.
        repo.remotes.origin.fetch()

        # Count commits ahead.
        commit_count = sum(1 for _ in repo.iter_commits(f"{repo.active_branch}..origin/{repo.active_branch}"))

        # Handle submodule.
        if check_git_access_token() and with_submodule and folder_exists_and_empty("./interface"):
            if folder_exists_and_empty("./interface"):
                logger.info("Empty interface folder detected. Trying to initialize submodule...")
                try:
                    repo.git.submodule("update", "--init", "--recursive")
                    logger.info("Successfully cloned interface submodule. Restarting...")
                    restart_application()
                except Exception as e:
                    logger.error("Could not initialize interface submodule: {0}"
                                 .format(str(e)), exc_info=config.EXC_INFO)

    except Exception as e:
        logger.error("Update check failed: {0}".format(str(e)), exc_info=config.EXC_INFO)
    finally:
        return commit_count


def update_app() -> str:
    """
    Pulls updates and restarts if needed.

    :return: Status message.
    """
    if not git:
        return "Git library is not available on the host system. Please install git to use the update functionality."

    commit_count = check_for_updates()

    if commit_count == 0:
        message = f"{config.APP_NAME} is already up-to-date."
        logger.info(message)
        return message

    try:
        repo = git.Repo("..")

        # Configure merge strategy to handle conflicts automatically.
        repo.git.config("merge.conflictStyle", "diff3")
        repo.git.config("merge.defaultToUpstream", "true")

        if check_git_access_token() and not folder_exists_and_empty("./interface"):
            logger.info("Updating app and submodules...")
            repo.git.submodule("update", "--init", "--recursive")
        else:
            logger.info("Updating app...")

        # Pull with automatic conflict resolution: use 'theirs' strategy with 'patience' diff algorithm.
        repo.remotes.origin.pull(strategy_option=["theirs", "patience"])

        # Refresh version info.
        check_for_updates(with_submodule=False)

        message = f"Successfully updated. {commit_count} new commit(s) applied."
        logger.info(message)
        restart_application()
        return message

    except Exception as e:
        message = f"Update failed: {e}"
        logger.error(message, exc_info=config.EXC_INFO)
        return message
