"""
The document store behind the configuration library and the mothership registry.

Both keep a flat list of dicts and query it one way only: a single field compared for
equality. That is the whole interface below, and it is the reason two backends can sit
behind it without a single branch at any call site.

**Why there are two.** tinydb is pinned in `requirements.txt`, so normally the file
backend is what runs. But it backs only saved *history* — the running pipeline is
loaded from a file in `/configuration` and never touches this — so an app that cannot
import tinydb has no business refusing to start, and no business refusing to save
either. In memory, everything works for as long as the process lives; what is lost is
the history across a restart, and `persistent` is how a client is told that.

The earlier version of this had no abstraction: every call site carried an
`if tinydb: ... else: <dict operation>`, nine of them in `configuration.py` alone. The
dict half had never run, and it silently discarded the operator's work without ever
saying so. Isolating the difference here is what makes the fallback honest — one
implementation to read, one flag to report, and callers that cannot tell them apart.
"""
import logging
import threading
from typing import Any

# Internal imports.
import config

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)

# Third-party imports (optional). See the module docstring.
try:
    import tinydb
except ImportError:
    tinydb = None


class Store:
    """
    A list of dicts, queried by one field at a time.

    Mirrors the subset of a `tinydb.table.Table` this app actually uses. Anything
    richer belongs in the caller, not here — the point is that the two backends stay
    trivially equivalent.
    """

    persistent: bool = True
    """Whether entries survive a restart. Reported as a capability by the api."""

    def insert(self, entry: dict) -> None:
        raise NotImplementedError

    def update(self, patch: dict, field: str, value: Any) -> int:
        """
        :returns: how many entries were changed.

        A count rather than tinydb's list of internal document ids. Every caller only
        ever asked whether it was non-empty, and those ids are meaningless outside the
        backend that minted them — returning them made the two implementations look
        like they disagreed when they did not.
        """
        raise NotImplementedError

    def remove(self, field: str, value: Any) -> int:
        """:returns: how many entries were removed. See {@link update}."""
        raise NotImplementedError

    def search(self, field: str, value: Any) -> list[dict]:
        raise NotImplementedError

    def get(self, field: str, value: Any) -> dict | None:
        raise NotImplementedError

    def all(self) -> list[dict]:
        raise NotImplementedError

    def __iter__(self):
        return iter(self.all())


class TinyDbStore(Store):
    """Backed by a tinydb file."""

    persistent = True

    def __init__(self, path: str):
        self._db = tinydb.TinyDB(path)
        self.path = path

    def insert(self, entry: dict) -> None:
        self._db.insert(entry)

    def update(self, patch: dict, field: str, value: Any) -> int:
        return len(self._db.update(patch, tinydb.where(field) == value))

    def remove(self, field: str, value: Any) -> int:
        return len(self._db.remove(tinydb.where(field) == value))

    def search(self, field: str, value: Any) -> list[dict]:
        return self._db.search(tinydb.where(field) == value)

    def get(self, field: str, value: Any) -> dict | None:
        return self._db.get(tinydb.where(field) == value)

    def all(self) -> list[dict]:
        return self._db.all()


class MemoryStore(Store):
    """
    Backed by a list that lives as long as the process.

    Locked, because the callers are a queue worker thread, the mothership worker
    thread and — since the api's path operations became `def` — several request
    threads at once. tinydb does its own locking; this has to do its own too.
    """

    persistent = False

    def __init__(self):
        self._entries: list[dict] = []
        self._lock = threading.Lock()

    def insert(self, entry: dict) -> None:
        with self._lock:
            self._entries.append(dict(entry))

    def update(self, patch: dict, field: str, value: Any) -> int:
        with self._lock:
            hit = [e for e in self._entries if e.get(field) == value]
            for entry in hit:
                entry.update(patch)
            return len(hit)

    def remove(self, field: str, value: Any) -> int:
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.get(field) != value]
            return before - len(self._entries)

    def search(self, field: str, value: Any) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._entries if e.get(field) == value]

    def get(self, field: str, value: Any) -> dict | None:
        with self._lock:
            for entry in self._entries:
                if entry.get(field) == value:
                    return dict(entry)
            return None

    def all(self) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._entries]


def open_store(path: str, description: str) -> Store:
    """
    The file store, or the in-memory one when tinydb is not installed.

    :param path: Where the file store would live.
    :param description: What this store holds, for the log line.
    """
    if tinydb is not None:
        return TinyDbStore(path)

    logger.warning("tinydb is not installed, so %s is kept in memory only and is lost when this "
                   "app restarts. Everything else, including the running pipeline, is unaffected — "
                   "the active configuration is loaded from a file, not from here. "
                   "Install it with 'pip install tinydb' to keep it.", description)
    return MemoryStore()
