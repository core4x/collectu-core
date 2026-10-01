# Tests

The tests use `unittest` and nothing else the app does not need. Run all of them from this folder:

```
python test.py
```

CI runs them on Python 3.11 and 3.13 and reports their coverage in the summary of each run. To measure the same
locally (`coverage` is not in `src/requirements.txt`):

```
pip install coverage
python -m coverage run test.py
python -m coverage report
```

To run some of them, name them: `python test.py test.utils.test_utils_hierarchy` runs one module,
`python test.py test.utils.test_utils_hierarchy.TestRefresh` one class of it.

## Layout

The folders follow `src`: `configuration`, `models`, `modules` and `utils` test what is named alike there, and
`others` holds the tests of the remaining files - `main.py`, `config.py` and `metrics.py` among them.
`api` and `media_types` test the `interface` submodule and are skipped where it is not checked out, as in CI.

## Writing a test

The app keeps its state in module globals (`data_layer`, the metrics registry, `os.environ`) and reads and writes
its files relative to the directory it runs from. `helpers.py` has what keeps the tests from leaking into each other:

- `GlobalStateTestCase` puts `data_layer`, the metrics registry and the environment variables back after each test.
  `patch_config` changes a constant of `config.py` for one test, and `enter_app_directory` runs it in a directory of
  its own, laid out like a checkout.
- `AppTestCase` additionally registers the fake modules and creates a `Configuration` the way `main.py` does. A
  configuration is written with `module_config`, and a running module is found with `instance`.
- The fake modules (`Client`, `ClientVariable`, `ClientTag`, `Source`, `Multiplier`, `Collector` and `Buffer`)
  follow the contract of real modules. Their data comes from the test, through `emit`, and arrives in an `Inbox`.

Nothing waits a fixed time for another thread: `wait_for` and `Inbox.wait_for` return as soon as the condition holds.
A test never reaches the hub - its session is stood in for - and leaves no file behind in the checkout.
