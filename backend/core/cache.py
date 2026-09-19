"""
In-process TTL cache whose key ALWAYS includes the active tenant.

A cache shared across tenants is a data leak waiting to happen (a zero-argument loader cached for
tenant A would be served to tenant B), so tenant scoping is not optional here: `require_tenant_id()`
runs on every call. Arguments whose name starts with an underscore are left out of the key (use them
for large, already-derived inputs such as DataFrames). Values are deep-copied in and out so a caller
mutating a result can never corrupt what the next caller receives.
"""
from __future__ import annotations

import copy
import datetime as dt
import functools
import inspect
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from backend.core.request_context import require_tenant_id


def _stable(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(map(repr, value))
    return repr(value)


def tenant_cache(ttl: float = 600.0, maxsize: int = 256) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        signature = inspect.signature(fn)
        store: OrderedDict[tuple[str, str], tuple[float, Any]] = OrderedDict()
        lock = threading.Lock()

        def make_key(args: tuple, kwargs: dict) -> tuple[str, str]:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            hashed = {k: v for k, v in bound.arguments.items() if not k.startswith("_")}
            return str(require_tenant_id()), json.dumps(hashed, default=_stable, sort_keys=True)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = make_key(args, kwargs)
            now = time.monotonic()
            with lock:
                hit = store.get(key)
                if hit and now - hit[0] < ttl:
                    store.move_to_end(key)
                    return copy.deepcopy(hit[1])
            value = fn(*args, **kwargs)
            with lock:
                store[key] = (now, copy.deepcopy(value))
                store.move_to_end(key)
                while len(store) > maxsize:
                    store.popitem(last=False)
            return value

        def clear() -> None:
            with lock:
                store.clear()

        wrapper.clear = clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
