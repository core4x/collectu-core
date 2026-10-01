"""
The small helpers: utils.analyzers, for looking into the running app, and utils.resilient_session, the session all
requests to the hub and the motherships go through.
"""
import unittest

# Internal imports.
import utils.analyzers
import utils.resilient_session


class TestAnalyzers(unittest.TestCase):

    def test_timing_logs_the_duration_and_keeps_the_function_as_it_is(self):
        @utils.analyzers.timing
        def add(first: int, second: int) -> int:
            """Adds."""
            return first + second

        with self.assertLogs(utils.analyzers.logger, level="INFO") as logs:
            self.assertEqual(add(1, second=2), 3)
        self.assertEqual((add.__name__, add.__doc__), ("add", "Adds."))
        self.assertRegex(logs.output[0], r"The function 'add' took \d+\.\d{3} ms for execution")

    def test_the_running_threads_are_logged_once(self):
        with self.assertLogs(utils.analyzers.logger, level="INFO") as logs:
            utils.analyzers.log_all_threads()
        self.assertEqual(len(logs.output), 1)
        self.assertIn("MainThread (daemon: False)", logs.output[0])


class TestResilientSession(unittest.TestCase):
    """
    A request is retried once on a network error and on the status codes saying "try again later".
    """

    def setUp(self):
        self.session = utils.resilient_session.create_resilient_session()
        self.addCleanup(self.session.close)

    def test_requests_are_retried_once(self):
        retry = self.session.get_adapter("https://api.collectu.de").max_retries
        self.assertEqual((retry.total, retry.connect, retry.read), (1, 1, 1))
        self.assertEqual(set(retry.status_forcelist), {429, 500, 502, 503, 504})
        self.assertEqual(retry.backoff_factor, 0.5)
        self.assertFalse(retry.raise_on_status, "The caller decides what an error status means.")
        self.assertTrue(retry.respect_retry_after_header)
        self.assertIsNone(retry.allowed_methods, "Every method is retried, not only the idempotent ones.")

    def test_both_schemes_are_retried(self):
        self.assertIs(self.session.get_adapter("http://mothership:8181"),
                      self.session.get_adapter("https://api.collectu.de"))

    def test_connections_are_pooled_for_many_threads(self):
        adapter = self.session.get_adapter("https://api.collectu.de")
        self.assertEqual((adapter._pool_connections, adapter._pool_maxsize), (100, 100))


if __name__ == '__main__':
    unittest.main()
