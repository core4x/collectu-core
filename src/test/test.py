"""
Execute all tests.
"""
import unittest
import os
import sys


if __name__ == '__main__':
    # Set /src as working directory.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Test initialization.
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="test")
    runner = unittest.TextTestRunner(verbosity=2)

    # Execute the single tests.
    result = runner.run(suite)

    if result.wasSuccessful():
        exit(0)
    else:
        exit(1)
