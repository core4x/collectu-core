"""
Per-module and pipeline-level performance metrics.
"""
import queue as _queue_module
import statistics
import threading
import time
from typing import Dict, Optional
import collections


class _SlidingWindow:
    """
    Thread-safe event counter.
    Records event timestamps in a rolling deque and prunes entries older than
    ``window`` seconds on every write so the deque never grows unboundedly.

    The total counter is separate and monotonically increasing - it is never
    pruned and represents the lifetime count since the object was created.
    """

    def __init__(self, window: float = 60.0) -> None:
        self._lock = threading.Lock()
        self._window = window
        self._total: int = 0
        self._dq: collections.deque[float] = collections.deque()

    def record(self) -> None:
        """
        Record one event at the current monotonic time.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            self._total += 1
            self._dq.append(now)
            while self._dq and self._dq[0] < cutoff:
                self._dq.popleft()

    def rate(self, window: Optional[float] = None) -> float:
        """
        Events per second over the given *window* (seconds).
        Defaults to the full constructor window when *window* is None.
        Returns 0.0 for a zero-length window.
        """
        w = window if window is not None else self._window
        if w <= 0:
            return 0.0
        cutoff = time.monotonic() - w
        with self._lock:
            count = sum(1 for t in self._dq if t >= cutoff)
        return count / w

    @property
    def total(self) -> int:
        """
        Monotonically increasing lifetime event count.
        """
        with self._lock:
            return self._total


class _CircularStats:
    """
    Rolling circular buffer of float samples (e.g. latencies in seconds).

    Retains the most recent ``maxlen`` values and computes mean and arbitrary
    percentiles on demand.  All operations are O(maxlen) in the worst case;
    for typical ``maxlen`` values (≤ 2 000) this is negligible.
    """

    def __init__(self, maxlen: int = 1_000) -> None:
        self._lock = threading.Lock()
        self._buf: collections.deque[float] = collections.deque(maxlen=maxlen)

    def record(self, value: float) -> None:
        """
        Append a sample, evicting the oldest if the buffer is full.
        """
        with self._lock:
            self._buf.append(value)

    def percentile(self, p: float) -> Optional[float]:
        """
        Returns the *p*-th percentile (0–100) using the nearest-rank method.
        Returns ``None`` when no samples have been recorded yet.
        """
        with self._lock:
            if not self._buf:
                return None
            sorted_buf = sorted(self._buf)
        idx = max(0, min(int(len(sorted_buf) * p / 100.0), len(sorted_buf) - 1))
        return sorted_buf[idx]

    @property
    def mean(self) -> Optional[float]:
        """
        Arithmetic mean of the current window.
        ``None`` when empty.
        """
        with self._lock:
            if not self._buf:
                return None
            return statistics.mean(self._buf)

    @property
    def count(self) -> int:
        """
        Number of samples currently held in the buffer (≤ maxlen).
        """
        with self._lock:
            return len(self._buf)


class _AtomicInt:
    """
    Monotonically increasing thread-safe integer counter.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: int = 0

    def inc(self, n: int = 1) -> None:
        with self._lock:
            self._value += n

    @property
    def value(self) -> int:
        with self._lock:
            return self._value


class ModuleMetrics:
    """
    All runtime metrics for a single module instance.

    Obtain instances exclusively via ``metrics_registry.register()`` to ensure
    that every module_id maps to exactly one object.
    """

    def __init__(
            self,
            module_id: str,
            module_name: str,
            queue: Optional[_queue_module.Queue] = None,
    ) -> None:
        self.module_id = module_id
        self.module_name = module_name
        self._queue = queue  # live reference enables queue-depth sampling in snapshot()

        ### Throughput ###
        self._received = _SlidingWindow()  # objects entering run()
        self._processed = _SlidingWindow()  # objects successfully through _run()

        ### Latency ###
        # Time inside _run() for one data object.
        self._proc_time = _CircularStats(maxlen=1_000)
        # Time the data sat in the inter-module ModuleWorker queue
        # (from _call_links() submit → run() invocation).
        self._link_wait = _CircularStats(maxlen=1_000)
        # Time the data sat in the module's *own* internal queue
        # (output modules; thread-safe processor modules).
        self._int_wait = _CircularStats(maxlen=1_000)

        self._errors = _AtomicInt()
        self._drops = _AtomicInt()

    def record_received(self) -> None:
        """
        Call once at the very top of run() for every data object that enters
        the module, before any validation or queuing.
        """
        self._received.record()

    def record_processed(self) -> None:
        """
        Call once per data object that successfully completes _run().
        For output modules call this after _run() returns without raising.
        For processor modules call this before _call_links() so that a link
        error does not inflate the count.
        """
        self._processed.record()

    def record_processing_time(self, seconds: float) -> None:
        """
        Wall-clock duration of a single _run() invocation in seconds.

        Example::

            t0 = time.monotonic()
            _run(data)
            self._metrics.record_processing_time(time.monotonic() - t0)
        """
        if seconds >= 0:
            self._proc_time.record(seconds)

    def record_link_wait(self, seconds: float) -> None:
        """
        Time (seconds) the data object spent in the ModuleWorker queue before this module's run() was invoked.

        Set ``data._metrics_link_ts = time.monotonic()`` in _call_links()
        immediately before submitting to the worker, then call this at the
        top of run() with ``time.monotonic() - data._metrics_link_ts``.
        """
        if seconds >= 0:
            self._link_wait.record(seconds)

    def record_internal_wait(self, seconds: float) -> None:
        """
        Time (seconds) the data object spent in the module's *own* internal
        queue (output modules / thread-safe processor modules).

        Set ``data._metrics_int_ts = time.monotonic()`` before ``queue.put(data)``
        and call this with ``time.monotonic() - data._metrics_int_ts`` after ``queue.get()`` returns.
        """
        if seconds >= 0:
            self._int_wait.record(seconds)

    def record_error(self) -> None:
        """
        Increment the error counter.
        Call from every except block that catches a processing failure rather than a drop or validation error.
        """
        self._errors.inc()

    def record_drop(self) -> None:
        """
        Increment the drop counter.
        Call whenever a data object is silently discarded because the queue has reached its stop limit.
        """
        self._drops.inc()

    def snapshot(self) -> dict:
        """
        Returns a fully JSON-serializable dict of all current metric values.

        Latency values are reported in milliseconds.
        Rate values are reported in objects / second.
        The queue depth is sampled live from the queue reference (if provided).
        """

        def _ms(v: Optional[float]) -> Optional[float]:
            return round(v * 1_000.0, 3) if v is not None else None

        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "throughput": {
                "received_per_sec_1s": round(self._received.rate(1), 2),
                "received_per_sec_10s": round(self._received.rate(10), 2),
                "received_per_sec_60s": round(self._received.rate(60), 2),
                "received_total": self._received.total,
                "processed_per_sec_1s": round(self._processed.rate(1), 2),
                "processed_per_sec_10s": round(self._processed.rate(10), 2),
                "processed_per_sec_60s": round(self._processed.rate(60), 2),
                "processed_total": self._processed.total,
            },
            "processing_time_ms": {
                "p50": _ms(self._proc_time.percentile(50)),
                "p95": _ms(self._proc_time.percentile(95)),
                "p99": _ms(self._proc_time.percentile(99)),
                "mean": _ms(self._proc_time.mean),
                "sample_count": self._proc_time.count,
            },
            "link_queue_wait_ms": {
                # Time between _call_links() submitting and this module's run() being called.
                "p50": _ms(self._link_wait.percentile(50)),
                "p95": _ms(self._link_wait.percentile(95)),
                "p99": _ms(self._link_wait.percentile(99)),
                "mean": _ms(self._link_wait.mean),
                "sample_count": self._link_wait.count,
            },
            "internal_queue_wait_ms": {
                # Time between run() queuing data and _process_queue() consuming it
                # (output modules and thread-safe processor modules only).
                "p50": _ms(self._int_wait.percentile(50)),
                "p95": _ms(self._int_wait.percentile(95)),
                "p99": _ms(self._int_wait.percentile(99)),
                "mean": _ms(self._int_wait.mean),
                "sample_count": self._int_wait.count,
            },
            "queue": {
                # Live depth of the module's own internal queue (None if not applicable).
                "current_depth": self._queue.qsize() if self._queue is not None else None,
            },
            "errors": {
                "error_total": self._errors.value,
                "drop_total": self._drops.value,
            },
        }


class MetricsRegistry:
    """
    Singleton that owns all ``ModuleMetrics`` instances and the pipeline-level
    end-to-end latency tracker.

    All methods are thread-safe.
    """

    _instance: Optional["MetricsRegistry"] = None
    _class_lock = threading.Lock()

    def __new__(cls) -> "MetricsRegistry":
        with cls._class_lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._modules: Dict[str, ModuleMetrics] = {}
                obj._module_lock = threading.Lock()
                obj._e2e = _CircularStats(maxlen=2_000)
                cls._instance = obj
        return cls._instance

    def register(
            self,
            module_id: str,
            module_name: str,
            queue: Optional[_queue_module.Queue] = None,
    ) -> ModuleMetrics:
        """
        Returns the ``ModuleMetrics`` for *module_id*, creating it on first call.

        Safe to call concurrently from multiple threads.

        :param module_id:   Unique module identifier (``configuration.id``).
        :param module_name: Human-readable name (``configuration.module_name``).
        :param queue:       Pass the module's internal ``queue.Queue`` to enable
                            live queue-depth reporting in ``snapshot()``.
        :returns: The (possibly newly created) ``ModuleMetrics`` for this module.
        """
        with self._module_lock:
            if module_id not in self._modules:
                self._modules[module_id] = ModuleMetrics(
                    module_id=module_id,
                    module_name=module_name,
                    queue=queue,
                )
            return self._modules[module_id]

    # TODO: What happens if a module is inactive.
    # TODO: What happens if a module is stopped.

    def record_end_to_end(self, seconds: float) -> None:
        """
        Record one end-to-end pipeline latency sample.

        Call from the output module's ``_process_queue()`` once ``_run()``
        completes successfully::

            created = getattr(data, '_metrics_ts', None)
            if created is not None:
                metrics_registry.record_end_to_end(time.monotonic() - created)

        ``_metrics_ts`` is stamped on the data in ``_call_links()`` the first
        time any module forwards it downstream.
        """
        if seconds >= 0:
            self._e2e.record(seconds)

    def snapshot(self) -> dict:
        """
        Full JSON-serializable snapshot of all per-module and pipeline metrics.

        Suitable for logging, exposing via an HTTP endpoint, or writing to a time-series database.
        """

        def _ms(v: Optional[float]) -> Optional[float]:
            return round(v * 1_000.0, 3) if v is not None else None

        with self._module_lock:
            modules = [m.snapshot() for m in self._modules.values()]

        return {
            "modules": modules,
            "pipeline": {
                "end_to_end_latency_ms": {  # TODO: I think the e2e is not clear, since we can have multiple flows involving different modules etc. So we should distinguish each possible flow.
                    "p50": _ms(self._e2e.percentile(50)),
                    "p95": _ms(self._e2e.percentile(95)),
                    "p99": _ms(self._e2e.percentile(99)),
                    "mean": _ms(self._e2e.mean),
                    "sample_count": self._e2e.count,
                },
            },
        }


metrics_registry = MetricsRegistry()
"""
The single application-wide metrics registry.

Import this object wherever metrics need to be recorded or read:

    from metrics import metrics_registry

In module base classes:

    self._metrics = metrics_registry.register(
        module_id   = configuration.id,
        module_name = configuration.module_name,
        queue       = self.queue,
    )

To read all metrics (e.g. from a status endpoint):

    import json
    print(json.dumps(metrics_registry.snapshot(), indent=2))
"""
