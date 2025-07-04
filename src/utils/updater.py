"""
This function auto-updates the app using a git repository.
This will only work, if the app was checked-out via git (and not downloaded).
"""
import os
import sys
import logging
import subprocess

# Internal imports.
import config
import data_layer
import main

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
    main.exit_handler()
    # os.execl(sys.executable, '"{}"'.format(sys.executable), *sys.argv)
    os.execv(sys.executable, ['python'] + sys.argv)


def find_file_by_filename(searched_file) -> str | None:
    """
    Returns the absolute path of the filename if it exists in the parent directory.

    :param searched_file: The filename of the searched file.
    :return: The absolute path if found, otherwise None.
    """
    parent_dir = "../"
    for filename in os.listdir(parent_dir):
        if filename.startswith(searched_file):
            return os.path.abspath(os.path.join(parent_dir, filename)).replace("\\", "/")
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
                os.chmod(find_file_by_filename("git_access_token"), 0o600)
                os.environ['GIT_SSH_COMMAND'] = (f'ssh -i {find_file_by_filename("git_access_token")} '
                                                 f'-o UserKnownHostsFile=/dev/null '
                                                 f'-o StrictHostKeyChecking=no '
                                                 f'-o IdentitiesOnly=yes')
                valid = True
    except Exception as e:
        logger.error("Could not check git update functionality requirements: {0}".format(str(e)),
                     exc_info=config.EXC_INFO)
        valid = False
    finally:
        return valid


def check_for_updates_with_git(with_submodule: bool = True) -> int | None:
    """
    Check for new commits in the online repository.
    If a git access token is provided and the interface module is empty, it is initially pulled.

    :param with_submodule: Check for an empty submodule (interface) folder and clone it if necessary.
    :returns: If there are possible updates (commits) the number of open commits is returned.
    If the app is up-to-date, 0 is returned.
    Otherwise, if something went wrong, None is returned.
    """
    commit_count = 0
    try:
        # There should always be a git folder...
        if not os.path.isdir('../.git'):
            logger.warning('No git repository found. Can not check for updates.')
            return None

        # Open the repository.
        repo = git.Repo("..")

        # Get the current version.
        result = subprocess.run("git describe --abbrev=7 --always --long --match v* main",
                                stdout=subprocess.PIPE, shell=True, universal_newlines=True)
        data_layer.version = result.stdout.strip()

        repo.remotes.origin.fetch()
        # Get the commit count of the current branch.
        commit_count = len(list(repo.iter_commits(f"{repo.active_branch.name}..origin/{repo.active_branch.name}")))

        if check_git_access_token() and folder_exists_and_empty("./interface") and with_submodule:
            try:
                logger.info("While checking for updates, we identified an empty interface folder. "
                            "Trying to clone interface submodule...")
                repo.git.submodule('update', '--init', '--recursive')
                logger.info("Successfully cloned interface submodule.")
            except Exception as e:
                logger.error("Could not clone interface submodule: {0}".format(str(e)), exc_info=config.EXC_INFO)
    except Exception as e:
        logger.error("Could not check for updates. Something unexpected went wrong: {0}".format(str(e)),
                     exc_info=config.EXC_INFO)
    finally:
        return commit_count


def update_app_with_git() -> str:
    """
    Update the app using git pull.

    :returns: A message containing information about the update process.
    """
    try:
        check_for_updates_with_git()
        repo = git.Repo("..")
        if check_git_access_token() and not folder_exists_and_empty("./interface"):
            logger.info("Updating app and interface submodule...")
            try:
                repo.git.submodule("update", "--init", "--recursive")
            except Exception as e:
                logger.error("Could not update interface submodule: {0}".format(str(e)), exc_info=config.EXC_INFO)
            repo.remotes.origin.pull()
            # The following is not working...
            # repo.remotes.origin.pull(recurse_submodules=True)
        else:
            logger.info("Updating app...")
            repo.remotes.origin.pull()
        # Update the version.
        check_for_updates_with_git(with_submodule=False)
        message = "Successfully finished update."
        restart_application()
        logger.info(message)
        return message
    except Exception as e:
        message = "Could not update app: {0}".format(str(e))
        logger.error(message, exc_info=config.EXC_INFO)
        return message
