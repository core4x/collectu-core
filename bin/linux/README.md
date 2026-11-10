# Run Collectu Core on Linux

| Script                       | What it does                                                                    |
|------------------------------|---------------------------------------------------------------------------------|
| `install_local.sh`           | Creates the virtual environment `venv` and installs the requirements.           |
| `start_local.sh`             | Starts the app in the terminal and starts it again when it crashes.             |
| `start_local_background.sh`  | Starts the app in the background. It keeps running when the terminal is closed. |
| `stop_local_background.sh`   | Stops the app started in the background.                                        |

The scripts can be called from any directory. Arguments given to the start scripts are passed on to
`main.py`.

If a script is not executable, make it so:

```
chmod +x bin/linux/*.sh
```

## Background execution

`start_local_background.sh` writes the process id of the app to `collectu.pid` in the root directory.
`stop_local_background.sh` stops that process and no other. It asks the app to end and only ends it by
force if it has not done so after 30 seconds.

What the app prints is written to `logs/console.log`, which starts empty with every start:

```
tail -f logs/console.log
```
