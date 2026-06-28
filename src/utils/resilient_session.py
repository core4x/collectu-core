import logging

# Third-party import.
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

logging.getLogger("urllib3").setLevel(logging.ERROR)
"""Overwrite urllib logger."""


def create_resilient_session():
    """
    Creates a resilient session, which retries on common exceptions.
    """
    session = requests.Session()

    retry = Retry(
        total=1,
        connect=1,
        read=1,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"],
        raise_on_status=False,
        respect_retry_after_header=True
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=100,
        pool_maxsize=100
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.request = lambda *args, **kwargs: requests.Session.request(
        session,
        *args,
        **kwargs
    )

    return session
