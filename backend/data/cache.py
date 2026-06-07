"""
Result cache with TTL — disk-backed (diskcache) for survival across restarts,
falling back to an in-memory dict if diskcache is not installed.

Key improvements over v1
------------------------
* Disk-backed: restarting the backend doesn't wipe all cached results, so
  the first user after a deploy gets the same fast response as everyone else.
* Exact namespace invalidation: invalidate("forecast") only deletes keys
  whose namespace is exactly "forecast" — no accidental substring wipes (B2).
* Thread-safe: diskcache uses SQLite with write-ahead logging; in-memory
  fallback is protected by threading.Lock.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "api"


def _make_key(namespace: str, params: dict) -> str:
    """Stable key: namespace as a readable prefix + md5(params) for uniqueness.
    The prefix enables exact namespace invalidation without iterating all keys."""
    params_hash = hashlib.md5(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f"{namespace}:{params_hash}"


class ResultCache:
    """Unified cache interface backed by diskcache, with in-memory fallback."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache = None     # diskcache.Cache instance or None
        self._mem:  dict       = {}    # fallback in-memory store
        self._lock = threading.Lock()
        self._init_disk_cache()

    def _init_disk_cache(self) -> None:
        try:
            import diskcache  # noqa: F401
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            import diskcache as dc
            self._cache = dc.Cache(str(_CACHE_DIR), size_limit=512 * 1024 * 1024)  # 512 MB
            log.info("Disk-backed cache initialised at %s", _CACHE_DIR)
        except ImportError:
            log.warning(
                "diskcache not installed — using in-memory cache. "
                "Run: pip install diskcache>=5.6.0"
            )
        except Exception as exc:
            log.warning("Disk cache init failed (%s) — using in-memory cache.", exc)

    # ── Public API (identical to old ResultCache) ──────────────────────

    def get(self, namespace: str, params: dict) -> Optional[Any]:
        k = _make_key(namespace, params)
        if self._cache is not None:
            return self._cache.get(k)   # returns None on miss or expiry
        # In-memory fallback
        with self._lock:
            entry = self._mem.get(k)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() < expires_at:
                return value
            del self._mem[k]
            return None

    def set(self, namespace: str, params: dict, value: Any,
            ttl: Optional[int] = None) -> None:
        k   = _make_key(namespace, params)
        exp = ttl or self.default_ttl
        if self._cache is not None:
            self._cache.set(k, value, expire=exp)
        else:
            with self._lock:
                self._mem[k] = (value, time.time() + exp)

    def invalidate(self, namespace: str) -> None:
        """Delete all keys that belong to `namespace` — exact match, not substring."""
        prefix = f"{namespace}:"
        if self._cache is not None:
            keys = [k for k in self._cache if isinstance(k, str) and k.startswith(prefix)]
            for k in keys:
                self._cache.delete(k)
        else:
            with self._lock:
                to_del = [k for k in self._mem if k.startswith(prefix)]
                for k in to_del:
                    del self._mem[k]

    def clear(self) -> None:
        if self._cache is not None:
            self._cache.clear()
        else:
            with self._lock:
                self._mem.clear()

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()


cache = ResultCache(default_ttl=600)
