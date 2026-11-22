"""Per-visitor and global sliding-window rate limits for /search.

In memory and per process, which is enough for one backend behind a tunnel.
Proxy headers are trusted only when the request arrives from this machine
(the tunnel connects over loopback); anyone else could forge them.
"""
from __future__ import annotations

import ipaddress
import threading
import time
from collections import deque
from typing import Deque, Dict, Mapping, Optional, Tuple

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = {}
_WINDOW = 60.0
_MAX_KEYS = 10_000
GLOBAL_KEY = "__all_visitors__"


def is_loopback(host: Optional[str]) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_proxied(headers: Mapping[str, str]) -> bool:
    return bool(headers.get("cf-connecting-ip") or headers.get("x-forwarded-for"))


def client_key(headers: Mapping[str, str], peer: Optional[str]) -> str:
    """The visitor's address. Behind the local tunnel, use the address the tunnel
    reports (CF-Connecting-IP, else the last X-Forwarded-For entry); otherwise
    use the socket peer and ignore forwarding headers."""
    if is_loopback(peer):
        cf = (headers.get("cf-connecting-ip") or "").strip()
        if cf:
            return cf
        xff = headers.get("x-forwarded-for") or ""
        last = xff.split(",")[-1].strip()
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
