"""Per-visitor sliding-window rate limit for /search.

In memory and per process, which is enough for one backend behind a tunnel.
Behind a proxy the visitor is the last X-Forwarded-For entry (the address the
proxy itself saw); without one it is the socket peer.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = {}
_WINDOW = 60.0
_MAX_KEYS = 10_000


def client_key(forwarded_for: Optional[str], peer: Optional[str]) -> str:
    if forwarded_for:
        last = forwarded_for.split(",")[-1].strip()
        if last:
            return last
    return peer or "unknown"


def check(key: str, limit: int, now: Optional[float] = None) -> Tuple[bool, int]:
    """Record a request. Returns (allowed, seconds_until_retry)."""
    if limit <= 0:
        return True, 0
    now = time.monotonic() if now is None else now
    with _lock:
        if len(_hits) > _MAX_KEYS:
            for k in [k for k, q in _hits.items() if not q or now - q[-1] > _WINDOW]:
                del _hits[k]
        q = _hits.setdefault(key, deque())
        while q and now - q[0] > _WINDOW:
            q.popleft()
        if len(q) >= limit:
            return False, max(1, int(_WINDOW - (now - q[0])) + 1)
        q.append(now)
        return True, 0


def reset() -> None:
    with _lock:
        _hits.clear()
