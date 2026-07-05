"""
Per-module and pipeline-level performance metrics.

Timestamps and flow metadata for in-flight data objects are stored out-of-band
in `data_context_map`, keyed by object identity. The data object itself is
never touched, so `data.__dict__` and any serialization path remain completely clean.

Per-module runtime metrics
---------------------------
Each module instance owns a `ModuleMetrics` object, obtained once via
`metrics_registry.register()`, which tracks:

* throughput      - rolling received/processed event rates (`_SlidingWindow`)
                     at 1s/10s/60s windows, plus lifetime totals.
* processing time - wall-clock duration of each `_run()` call, held in a
                     fixed-size circular buffer (`_CircularStats`) with mean/percentile support.
* queue waits     - see "Two queue wait times" below.
* queue depth     - live size of the module's own internal queue, if any.
* errors / drops  - simple monotonic counters (`_AtomicInt`).

Two queue wait times
---------------------
link_wait     Time between `_call_links()` submitting data to the
              ModuleWorker queue and the downstream module's `run()`
              being invoked. Reflects inter-module backpressure.

internal_wait Time between `run()` putting data into the module's own
              internal queue and `_process_queue()` consuming it.
              Relevant for output modules and thread-safe processor modules.

Per-flow end-to-end latency
-----------------------------
The first time `_call_links()` forwards a data object, it records the
originating module's ID as the *flow key* in that object's `_DataContext`.
Each subsequent deep-copy carries the key forward (`_DataContextMap.propagate`),
along with the set of module ids already `visited`, so a module can check
`_DataContext.remaining()` to see whether forwarding from it would make any
further progress (versus hitting a sink or a closed loop). Ending modules
record the elapsed time under the flow key via
`metrics_registry.record_end_to_end()`, so `metrics_registry.snapshot()
["flows"]` gives one latency histogram per independent data flow through
the pipeline.

Registry and snapshotting
---------------------------
`MetricsRegistry` is a thread-safe, process-wide singleton
(`metrics_registry`) owning every `ModuleMetrics` instance plus the
per-flow latency trackers. `metrics_registry.snapshot()` returns a fully
JSON-serializable dict:

    {
      "modules": [ <ModuleMetrics.snapshot()>, ... ],
      "flows": {
        "<source_module_id>": {
          "end_to_end_latency_ms": {
            "p50": ..., "p95": ..., "p99": ..., "mean": ..., "sample_count": ...
          }
        },
        ...
      }
    }

All latency figures are reported in milliseconds; internal storage is in
seconds. Percentiles use nearest-rank over the current buffer contents and
return `None` once no samples have been recorded yet, so downstream
consumers don't need to special-case an empty pipeline.
"""
import queue as _queue_module
import statistics
import threading
import time
import weakref
from typing import Dict, Optional
import collections


class _DataContext:
    """
    External data-object timestamp context.

    Timestamps and flow metadata for one in-flight data object.
    Stored in `data_context_map` - never on the data object itself.
    """
    __slots__ = ('pipeline_ts', 'source_id', 'link_ts', 'internal_ts', 'visited')

    def __init__(self,
                 pipeline_ts: float,
                 source_id: str,
                 link_ts: float,
                 visited: frozenset[str] = frozenset(),
                 ) -> None:
        """
        :param pipeline_ts: Monotonic time at which the data left its source module.
        :param source_id: Originating module's `configuration.id`; doubles as the flow key.
        :param link_ts: Monotonic time at which the data entered the current link queue.
        :param visited: Module ids already traversed by this flow. Defaults to empty.
        """
        self.pipeline_ts: float = pipeline_ts
        """When data left its source module."""
        self.source_id: str = source_id
        """Originating module_id → flow key."""
        self.link_ts: float = link_ts
        """When data entered the link queue."""
        self.internal_ts: Optional[float] = None
        """When data entered the internal queue."""
        self.visited: frozenset[str] = visited
        """Module ids already traversed by this flow."""

    def remaining(self, links: set[str]) -> set[str]:
        """
        Returns the subset of *links* not yet visited by this data object.

        Empty result means forwarding from here produces no new progress -
        either because *links* is empty (a true sink) or because every link
        points back into a module already seen (a closed loop). Both cases
        mean "this is the end of the flow" for measurement purposes.

        :param links: The links.
        :returns: The remaining links.
        """
        return links - self.visited


class _DataContextMap:
    """
    Thread-safe identity-based store mapping live data objects to their
    `_DataContext`, without requiring the data object to be hashable.

    `models.Data` is a standard (non-frozen) dataclass, which Python makes unhashable by default.

    Entries are keyed by `id(data)` (always hashable - just an int)
    and cleaned up automatically via `weakref.finalize`, which only
    requires the object to support weak references, not to be hashable.
    """

    def __init__(self) -> None:
        """
        Initialize an empty, lock-protected id-to-context map.
        """
        self._lock = threading.Lock()
        """Guards all reads/writes of `_map`."""
        self._map: Dict[int, _DataContext] = {}
        """Maps `id(data)` to that object's `_DataContext`."""

    def get(self, data) -> Optional[_DataContext]:
        """
        Look up the context previously stored for *data*.

        :param data: The data object.
        :returns: The associated `_DataContext`, or `None` if *data* has no context.
        """
        with self._lock:
            return self._map.get(id(data))

    def set(self, data, ctx: _DataContext) -> None:
        """
        Store *ctx* for *data* and register a finalizer that removes the
        entry once *data* is garbage-collected.

        :param data: The data object.
        :param ctx: The data context.
        :returns: None.
        """
        key = id(data)
        with self._lock:
            self._map[key] = ctx
        try:
            weakref.finalize(data, self._cleanup, key)
        except TypeError:
            pass

    def _cleanup(self, key: int) -> None:
        """
        Delete the key from the map.

        :param key: The `id()` of the data object being finalized.
        :returns: None.
        """
        with self._lock:
            self._map.pop(key, None)

    def propagate(self, old_data, new_data) -> None:
        """
        Copy the context from `old_data` to `new_data` when a processor's
        `_run()` returns a brand-new data object instead of the same one.
        No-op if `old_data` has no context or `new_data` already has one.

        :param old_data: The old data object.
        :param new_data: The new data object.
        :returns: None.
        """
        if old_data is new_data:
            return
        ctx = self.get(old_data)
        if ctx is not None and self.get(new_data) is None:
            self.set(new_data, ctx)


data_context_map = _DataContextMap()
"""
Module-level singleton - the only instance used throughout the application.
"""


class _SlidingWindow:
    """
    Thread-safe event counter.

    Records event timestamps in a rolling deque pruned to `window` seconds on every write.
    `total` is a separate monotonically increasing lifetime counter.
    """

    def __init__(self,
                 window: float = 60.0) -> None:
        """
        :param window: Size in seconds of the rolling window used to prune old
            timestamps and as the default for `rate()`.
        """
        self._lock = threading.Lock()
        """Guards `_total` and `_dq`."""
        self._window = window
        """Default rolling-window size in seconds."""
        self._dq: collections.deque[float] = collections.deque()
        """Monotonic timestamps of events still within `_window` seconds of now."""
        self._total: int = 0
        """Lifetime count of events recorded, never pruned."""

    def record(self) -> None:
        """
        Record one event at the current monotonic time.

        :returns: None.
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

        :param window: The window size in seconds.
        :returns: The rate. 0.0 for a zero-length window.
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

        :returns: The total number of events ever recorded.
        """
        with self._lock:
            return self._total


class _CircularStats:
    """
    Fixed-size circular buffer of float samples with mean and percentile support.
    """

    def __init__(self, maxlen: int = 1_000) -> None:
        """
        :param maxlen: Maximum number of samples retained; oldest samples are
            evicted first once the buffer is full.
        """
        self._lock = threading.Lock()
        """Guards `_buf`."""
        self._buf: collections.deque[float] = collections.deque(maxlen=maxlen)
        """Circular buffer of the most recent samples, oldest evicted first."""

    def record(self, value: float) -> None:
        """
        Append a sample, evicting the oldest if the buffer is full.

        :param value: The value in seconds to append.
        :returns: None.
        """
        with self._lock:
            self._buf.append(value)

    def percentile(self, p: float) -> Optional[float]:
        """
        Nearest-rank percentile of the samples currently in the buffer.

        :param p: p-th percentile (0-100).
        :returns: Nearest-rank sample value. `None` when empty.
        """
        with self._lock:
            if not self._buf:
                return None
            s = sorted(self._buf)
        return s[max(0, min(int(len(s) * p / 100.0), len(s) - 1))]

    @property
    def mean(self) -> Optional[float]:
        """
        Arithmetic mean of the current window.
        `None` when empty.

        :returns: The mean of all samples currently in the buffer, or `None` if empty.
        """
        with self._lock:
            return statistics.mean(self._buf) if self._buf else None

    @property
    def count(self) -> int:
        """
        Number of samples currently held in the buffer (≤ maxlen).

        :returns: The current sample count.
        """
        with self._lock:
            return len(self._buf)


class _AtomicInt:
    """
    Monotonically increasing thread-safe integer counter.
    """

    def __init__(self) -> None:
        """
        Initialize the counter at zero.
        """
        self._lock = threading.Lock()
        """Guards `_value`."""
        self._value: int = 0
        """Current counter value."""

    def inc(self, n: int = 1) -> None:
        """
        Increment the counter.

        :param n: Amount to add to the counter. Defaults to 1.
        :returns: None.
        """
        with self._lock:
            self._value += n

    @property
    def value(self) -> int:
        """
        Current counter value.

        :returns: The current value of the counter.
        """
        with self._lock:
            return self._value


class ModuleMetrics:
    """
    All runtime metrics for a single module instance.
    Obtain via `metrics_registry.register()`.
    """

    def __init__(self,
                 module_id: str,
                 module_name: str,
                 queue: Optional[_queue_module.Queue] = None,
                 ) -> None:
        """
        :param module_id: Unique module identifier (`configuration.id`).
        :param module_name: Human-readable name (`configuration.module_name`).
        :param queue: The module's own internal queue, if any, used to report
            live queue depth in `snapshot()`.
        """
        self.module_id = module_id
        """Unique module identifier (`configuration.id`)."""
        self.module_name = module_name
        """Human-readable module name (`configuration.module_name`)."""
        self._queue = queue
        """The module's own internal queue, if any; used only for live depth reporting."""

        # Throughput.
        self._received = _SlidingWindow()
        """Rolling counter of data objects entering `run()`."""
        self._processed = _SlidingWindow()
        """Rolling counter of data objects that successfully completed `_run()`."""

        # Timing.
        self._proc_time = _CircularStats(maxlen=1_000)  # time inside _run()
        """Samples of wall-clock time spent inside `_run()`, in seconds."""
        self._link_wait = _CircularStats(maxlen=1_000)  # ModuleWorker queue wait
        """Samples of ModuleWorker queue wait time (link_wait), in seconds."""
        self._int_wait = _CircularStats(maxlen=1_000)  # internal queue wait
        """Samples of internal queue wait time (internal_wait), in seconds."""

        # Errors / drops.
        self._errors = _AtomicInt()
        """Lifetime count of processing errors."""
        self._drops = _AtomicInt()
        """Lifetime count of data objects dropped due to a full queue."""

    def record_received(self) -> None:
        """
        Call once per data object entering run(), before any queuing.

        :returns: None.
        """
        self._received.record()

    def record_processed(self) -> None:
        """
        Call once per data object successfully completing _run().

        :returns: None.
        """
        self._processed.record()

    def record_processing_time(self, seconds: float) -> None:
        """
        Record the wall-clock duration of one `_run()` call.

        :param seconds: Wall-clock duration in seconds of one _run() call.
        :returns: None.
        """
        if seconds >= 0:
            self._proc_time.record(seconds)

    def record_link_wait(self, seconds: float) -> None:
        """
        Record one ModuleWorker queue wait sample.

        :param seconds: Elapsed time in seconds between _call_links() submitting data and this module's
            run() being invoked (= ModuleWorker queue wait).
        :returns: None.
        """
        if seconds >= 0:
            self._link_wait.record(seconds)

    def record_internal_wait(self, seconds: float) -> None:
        """
        Record one internal queue wait sample.

        :param seconds: Elapsed time in seconds between run() queuing data and _process_queue() consuming
            it (output modules / thread-safe processor modules only).
        :returns: None.
        """
        if seconds >= 0:
            self._int_wait.record(seconds)

    def record_error(self) -> None:
        """
        Increment error counter (call from every processing except block).

        :returns: None.
        """
        self._errors.inc()

    def record_drop(self) -> None:
        """
        Increment drop counter (call when queue is full and data is discarded).

        :returns: None.
        """
        self._drops.inc()

    def snapshot(self) -> dict:
        """
        JSON-serializable snapshot of all current metrics (latencies in ms).

        :returns: A dict with `module_id`, `module_name`, `throughput`,
            `processing_time_ms`, `link_queue_wait_ms`, `internal_queue_wait_ms`,
            `queue`, and `errors` keys.
        """

        def _ms(v: Optional[float]) -> Optional[float]:
            """
            Convert a duration from seconds to rounded milliseconds.

            :param v: Duration in seconds, or `None`.
            :returns: Duration in milliseconds rounded to 3 decimals, or `None` if *v* is `None`.
            """
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
                # ModuleWorker queue: how long data waited before run() was called.
                "p50": _ms(self._link_wait.percentile(50)),
                "p95": _ms(self._link_wait.percentile(95)),
                "p99": _ms(self._link_wait.percentile(99)),
                "mean": _ms(self._link_wait.mean),
                "sample_count": self._link_wait.count,
            },
            "internal_queue_wait_ms": {
                # Module's own queue: how long data waited between run() and _run().
                # Only populated for output modules and thread-safe processor modules.
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
    Pipeline-level registry.

    Application-wide singleton that owns all `ModuleMetrics` instances and
    per-flow end-to-end latency trackers.

    Access via the module-level `metrics_registry` object.
    """

    _instance: Optional["MetricsRegistry"] = None
    """The single shared instance, created lazily on first `__new__()` call."""
    _class_lock = threading.Lock()
    """Guards creation of `_instance`."""

    def __new__(cls) -> "MetricsRegistry":
        """
        Return the shared `MetricsRegistry` instance, creating and
        initializing it on the first call.

        :returns: The application-wide `MetricsRegistry` singleton.
        """
        with cls._class_lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._modules: Dict[str, ModuleMetrics] = {}
                """Maps module_id to its `ModuleMetrics` instance."""
                obj._module_lock = threading.Lock()
                """Guards `_modules`."""
                # Per-flow E2E latency: keyed by source module_id.
                obj._flows: Dict[str, _CircularStats] = {}
                """Maps source module_id (flow key) to its end-to-end latency samples."""
                obj._flow_lock = threading.Lock()
                """Guards `_flows` (only for adding/removing keys; `_CircularStats` is self-locking)."""
                cls._instance = obj
        return cls._instance

    def register(
            self,
            module_id: str,
            module_name: str,
            queue: Optional[_queue_module.Queue] = None,
    ) -> ModuleMetrics:
        """
        Returns the `ModuleMetrics` for *module_id*, creating it on first call.
        Thread-safe.

        :param module_id: Unique module identifier (`configuration.id`).
        :param module_name: Human-readable name (`configuration.module_name`).
        :param queue: Pass the module's internal queue for live depth reporting.
        :returns: The `ModuleMetrics` instance for *module_id*.
        """
        with self._module_lock:
            if module_id not in self._modules:
                self._modules[module_id] = ModuleMetrics(
                    module_id=module_id,
                    module_name=module_name,
                    queue=queue,
                )
            return self._modules[module_id]

    def reset(self) -> None:
        """
        Discards all per-module and per-flow metrics collected so far.
        Intended to be called when a configuration is (re)started, so metrics from a
        previous run do not linger alongside the newly started modules. Thread-safe.

        :returns: None.
        """
        with self._module_lock:
            self._modules.clear()
        with self._flow_lock:
            self._flows.clear()

    def record_end_to_end(self, source_id: str, output_id: str, seconds: float) -> None:
        """
        Record one end-to-end latency sample for the flow identified by the
        (*source_id*, *output_id*) pair — a distinct histogram per source/sink combination.

        :param source_id: The configuration id of the originating module.
        :param output_id: The configuration id of the recording module at the end.
        :param seconds: Elapsed time in seconds between start and end of a flow.
        :returns: None.
        """
        key = f"{source_id}->{output_id}"
        if seconds < 0:
            return
        with self._flow_lock:
            if key not in self._flows:
                self._flows[key] = _CircularStats(maxlen=2_000)
        # Record outside the lock - _CircularStats is internally thread-safe.
        self._flows[key].record(seconds)

    def overall_performance(self) -> dict:
        """
        Overall performance KPI across all registered modules.

        For every module, the processed rate over the last 60 seconds is
        extrapolated to data objects per minute; min, max, and average are
        then taken across all modules. All values are `None` while no
        modules are registered, so downstream consumers don't need to
        special-case an empty pipeline.

        :returns: A flat dict with `processed_per_min_min`,
            `processed_per_min_max`, `processed_per_min_avg`, and the
            `module_count` the KPI was computed over.
        """
        with self._module_lock:
            modules = list(self._modules.values())

        rates = [m._processed.rate(60) * 60.0 for m in modules]
        if not rates:
            return {
                "processed_per_min_min": None,
                "processed_per_min_max": None,
                "processed_per_min_avg": None,
                "module_count": 0,
            }
        return {
            "processed_per_min_min": round(min(rates), 2),
            "processed_per_min_max": round(max(rates), 2),
            "processed_per_min_avg": round(statistics.mean(rates), 2),
            "module_count": len(rates),
        }

    def snapshot(self) -> dict:
        """
        Full JSON-serializable snapshot of all per-module and per-flow metrics.

        Structure:

        {
          "modules": [ <ModuleMetrics.snapshot()>, ... ],
          "flows": {
            "<source_module_id>": {
              "end_to_end_latency_ms": { "p50": ..., "p95": ..., "p99": ...,
                                         "mean": ..., "sample_count": ... }
            },
            ...
          }
        }

        :returns: A dict with a `modules` list and a `flows` dict, as described above.
        """

        def _ms(v: Optional[float]) -> Optional[float]:
            """
            Convert a duration from seconds to rounded milliseconds.

            :param v: Duration in seconds, or `None`.
            :returns: Duration in milliseconds rounded to 3 decimals, or `None` if *v* is `None`.
            """
            return round(v * 1_000.0, 3) if v is not None else None

        with self._module_lock:
            modules = [m.snapshot() for m in self._modules.values()]

        with self._flow_lock:
            flow_ids = list(self._flows.keys())

        flows = {}
        for fid in flow_ids:
            stats = self._flows[fid]
            flows[fid] = {
                "end_to_end_latency_ms": {
                    "p50": _ms(stats.percentile(50)),
                    "p95": _ms(stats.percentile(95)),
                    "p99": _ms(stats.percentile(99)),
                    "mean": _ms(stats.mean),
                    "sample_count": stats.count,
                }
            }

        return {"modules": modules, "flows": flows}


metrics_registry = MetricsRegistry()
"""
The single application-wide metrics registry.

Read all metrics:

    import json, time
    while True:
        print(json.dumps(metrics_registry.snapshot(), indent=2))
        time.sleep(10)
"""
