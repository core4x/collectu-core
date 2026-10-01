"""
Execute all tests, or the ones named, e.g. 'python test.py test.utils.test_utils_hierarchy'.
"""
import unittest
import os
import sys


if __name__ == '__main__':
    # Set /src as working directory.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Test initialization.
    loader = unittest.TestLoader()
    if len(sys.argv) > 1:
        suite = loader.loadTestsFromNames(sys.argv[1:])
    else:
        suite = loader.discover(start_dir="test")
    runner = unittest.TextTestRunner(verbosity=2)

    # Execute the single tests.
    result = runner.run(suite)

    if result.wasSuccessful():
        exit(0)
    else:
        exit(1)
