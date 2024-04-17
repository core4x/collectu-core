"""
This function auto-updates the app using a git repository.
This will only work, if the app was checked-out via git (and not downloaded).
"""
import os
import sys
import logging
from typing import Optional

# Internal imports.
import config
import data_layer

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""

# Third party imports.
try:
    import git
except Exception as e:
    logger.error("Git is not installed on the host system. To use the update functionality, please install git.")


def restart_application():
    """
    Restarts the application.
    """
    logger.info("Restarting application...")
    os.execl(sys.executable, '"{}"'.format(sys.executable), *sys.argv)


def find_file_by_filename(searched_file) -> str | None:
    """
    Returns the filename if it exists in the main directory.

    :param searched_file: The filename of the searched file.
    :return: The filename if found, otherwise none.
    """
    for filename in os.listdir("../"):
        if filename.startswith(searched_file):
            return filename
    return None


def folder_exists_and_empty(path) -> bool:
    """
    Checks if the folder for the given path exists and is empty.

    :param path: The path to the folder.
    :return: True if the folder exists and is empty, false otherwise.
    """
    if not os.path.exists(path):
        return False
    elif len(os.listdir(path)) == 0:
        return True
    else:
        return False


def check_git_access_token() -> bool:
    """
    Checks if there is a git repository and an access token. But not if the access token is valid.

    :returns: A boolean indicating if the requirements are satisfied.
    """
    valid = True
    try:
        if not os.path.isdir('../.git'):
            logger.error("Could not find local git repository. "
                         "Please clone the project to use the update functionality.")
            valid = False
        else:
            if not find_file_by_filename("git_access_token"):
                logger.error(f"You haven't a valid git access token for updating submodules (frontend and api). "
                             f"You can add your git access token by creating a file named 'git_access_token'. "
                             f"If you do not have a git access token, please subscribe to a plan or contact: "
                             f"{config.CONTACT}.")
                valid = False
            else:
                os.chmod(os.path.join("../", find_file_by_filename("git_access_token")), 0o600)
                os.environ['GIT_SSH_COMMAND'] = (f'ssh -i ./{find_file_by_filename("git_access_token")} '
                                                 f'-o UserKnownHostsFile=/dev/null '
                                                 f'-o StrictHostKeyChecking=no')
                valid = True
    except Exception as e:
        logger.error("Could not check git update functionality requirements: {0}".format(str(e)),
                     exc_info=config.EXC_INFO)
        valid = False
    finally:
        if not valid:
            # We send a notification if the usage statistic sender was instantiated.
            if data_layer.statistics:
                data_layer.statistics.send_invalid_update_attempt()
        return valid


def check_for_updates_with_git() -> Optional[int]:
    """
    Check for new commits in the online repository.

    :returns: If there are possible updates (commits) the number of open commits is returned.
    If the app is up-to-date, 0 is returned.
    Otherwise, if something went wrong, None is returned.
    """
    # There should always be a git folder...
    if not os.path.isdir('../.git'):
        logger.warning('No git repository found. Can not check for updates.')
        return None

    # Open the repository.
    repo = git.Repo("..")
    repo.remotes.origin.fetch()
    # Get the commit count of the current branch.
    commit_count = len(list(repo.iter_commits(f"{repo.active_branch.name}..origin/{repo.active_branch.name}")))

    if check_git_access_token():
        # Check for updates in submodules.
        for submodule in repo.submodules:
            try:
                submodule_repo = git.Repo(os.path.join("..", submodule.path))
                # Get the current HEAD commit.
                head_commit = submodule_repo.head.commit
                commit_count += len(list(submodule_repo.iter_commits(f"{head_commit}..origin/"f"{head_commit}")))
            except Exception as e:
                logging.error("Could not check for updates for submodule '{0}': {1}"
                              .format(submodule.name, str(e)), exc_info=config.EXC_INFO)
    return commit_count


def create_interface() -> None:
    """
    Pulls the interface (frontend and api) if it does not exist.
    """
    if folder_exists_and_empty("./interface") and check_git_access_token():
        # Initialize and update submodules.
        repo = git.Repo("..")
        repo.git.submodule('update', '--init', '--recursive')
        logger.info("Successfully cloned submodule.")


def update_app_with_git() -> str:
    """
    Update the app using git pull.

    :returns: A message containing information about the update process.
    """
    try:
        create_interface()
        possible_updates = check_for_updates_with_git()
        if possible_updates == 0:
            message = f"Cancelled update procedure. {config.APP_NAME} is already up to date."
            logger.info(message)
            return message
        elif not possible_updates:
            raise Exception("Cancelled update procedure. Please check the logs for further information.")
        else:
            repo = git.Repo("..")
            if os.environ.get("GIT_ACCESS_TOKEN", None):
                repo.remotes.origin.pull()
                repo.git.submodule('update', '--init', '--recursive', '--remote')
            else:
                repo.remotes.origin.pull()
            if data_layer.statistics:
                data_layer.statistics.send_successful_update()
            message = "Successfully finished update. Please restart the app."
            logger.info(message)
            return message
    except Exception as e:
        # We send a notification if the usage statistic sender was instantiated.
        if data_layer.statistics:
            data_layer.statistics.send_invalid_update_attempt()
        message = "Could not update app: {0}".format(str(e))
        logger.error(message, exc_info=config.EXC_INFO)
        return message
