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

        if not os.environ.get("GIT_ACCESS_TOKEN", None):
            logger.error(f"You haven't a valid git access token for updating {config.APP_NAME}. "
                         f"You can add your git access token in settings.ini. "
                         f"If you do not have a git access token, please contact: {config.CONTACT}.")
            valid = False
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
    Otherwise (something went wrong), None is returned.
    """
    commits_behind = None
    try:
        if check_git_access_token():
            # First do a git fetch, so we have possible changes in our local repository.
            git.cmd.Git().fetch()
            # If we use the one below, this is only working once?!
            # git.cmd.Git().fetch(f'https://oauth2:{os.environ.get("GIT_ACCESS_TOKEN")}@{config.GIT_LINK}',
            #                     config.GIT_BRANCH)
            # Subsequently we check the status.
            status = git.cmd.Git().status("--branch", "--porcelain").splitlines()[0]
            # If there are commits: ## development...origin/development [behind 1]
            # If there are no commits: ## development...origin/development
            if "[behind" in status:
                # Extract the number of commits behind.
                commits_behind = int(status[status.find("[behind ") + len("[behind "):status.rfind("]")])
            else:
                commits_behind = 0
        else:
            raise Exception("The system does not meet the requirements for using the update functionality. "
                            "Please check the logs for further information.")
    except Exception as e:
        logger.error("Could not check for updates: {0}".format(str(e)), exc_info=config.EXC_INFO)
    finally:
        return commits_behind


def update_app_with_git() -> str:
    """
    Update the app using git pull.

    :returns: A message containing information about the update process.
    """
    try:
        possible_updates = check_for_updates_with_git()
        if possible_updates == 0:
            message = f"Cancelled update procedure. {config.APP_NAME} is already up to date."
            logger.info(message)
            return message
        elif not possible_updates:
            raise Exception("Cancelled update procedure. Please check the logs for further information.")
        else:
            # Pull from remote origin to the current working directory.
            result = git.cmd.Git().pull(f'https://oauth2:{os.environ.get("GIT_ACCESS_TOKEN")}@{config.GIT_LINK}',
                                        config.GIT_BRANCH)
            if data_layer.statistics:
                data_layer.statistics.send_successful_update()
            message = "Successfully finished update: {0} - Please restart the app.".format(str(result))
            logger.info(message)
            return message
    except Exception as e:
        # We send a notification if the usage statistic sender was instantiated.
        if data_layer.statistics:
            data_layer.statistics.send_invalid_update_attempt()
        message = "Could not update app: {0}".format(str(e))
        logger.error(message, exc_info=config.EXC_INFO)
        return message
