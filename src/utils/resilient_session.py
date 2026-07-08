import logging

# Third-party imports.
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

logging.getLogger("urllib3").setLevel(logging.ERROR)


def create_resilient_session() -> requests.Session:
    """
    Creates a resilient session with automatic retries on network errors
    and common HTTP 5xx / 429 status codes.
    """
    session = requests.Session()

    retry = Retry(
        total=1,
        connect=1,
        read=1,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=100,
        pool_maxsize=100,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session
