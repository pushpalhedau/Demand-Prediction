"""
Simple in-memory result cache with TTL for expensive computations.
"""
from __future__ import annotations

import time
import hashlib
import json
from typing import Any, Optional


class ResultCache:
    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def _key(self, namespace: str, params: dict) -> str:
        raw = namespace + json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, namespace: str, params: dict) -> Optional[Any]:
        k = self._key(namespace, params)
        if k in self._store:
            value, expires_at = self._store[k]
            if time.time() < expires_at:
                return value
            del self._store[k]
        return None

    def set(self, namespace: str, params: dict, value: Any, ttl: Optional[int] = None) -> None:
        k = self._key(namespace, params)
        self._store[k] = (value, time.time() + (ttl or self.default_ttl))

    def invalidate(self, namespace: str) -> None:
        keys_to_delete = [k for k in self._store if namespace in k]
        for k in keys_to_delete:
            del self._store[k]

    def clear(self) -> None:
        self._store.clear()


cache = ResultCache(default_ttl=600)
