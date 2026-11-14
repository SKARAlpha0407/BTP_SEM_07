"""In-process request telemetry, exposed at GET /metrics.

Turns the 'warm ~1.4s vs cold ~8.6s' claim into numbers anyone can reproduce:
latency percentiles split by cache path, cache hit rate, and LLM calls saved
by the insight cache. Resets when the server restarts.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Deque, Dict

_lock = threading.Lock()
_latency: Dict[str, Deque[float]] = {}
_counters: Dict[str, int] = {}
_started = time.time()
_WINDOW = 1000


def incr(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def observe(name: str, seconds: float) -> None:
    with _lock:
        _latency.setdefault(name, deque(maxlen=_WINDOW)).append(seconds)


@contextmanager
def timer(name: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        observe(name, time.perf_counter() - t0)


def _pct(values, q: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return round(s[idx], 4)


def snapshot() -> dict:
    with _lock:
        counters = dict(_counters)
        lat = {k: list(v) for k, v in _latency.items()}
    searches = counters.get("search_total", 0)
    hits = counters.get("cache_hit", 0)
    wanted = counters.get("insights_requested", 0)
    cached = counters.get("insights_from_cache", 0)
    return {
        "uptime_seconds": round(time.time() - _started, 1),
        "counters": counters,
        "cache_hit_rate": round(hits / searches, 4) if searches else None,
        "insight_cache_rate": round(cached / wanted, 4) if wanted else None,
        "latency_seconds": {
            k: {
                "count": len(v),
                "p50": _pct(v, 0.50),
                "p95": _pct(v, 0.95),
                "mean": round(sum(v) / len(v), 4) if v else 0.0,
            }
            for k, v in lat.items()
        },
    }


def reset() -> None:
    with _lock:
        _latency.clear()
        _counters.clear()
