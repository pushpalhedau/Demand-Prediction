"""Small, dependency-free security primitives."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from backend.core.errors import AuthError


class LoginThrottle:
    """
    Sliding-window limiter for failed sign-ins, keyed by account (lower-cased email).

    Lives on the server, so reloading the page or opening a new session does not reset it. State is
    per process: behind several instances the effective limit is `max_failures` per instance, and the
    auth server's own rate limits remain the shared backstop.
    """

    def __init__(self, max_failures: int = 5, window_seconds: float = 900.0, lockout_seconds: float = 900.0):
        self.max_failures = max_failures
        self.window = window_seconds
        self.lockout = lockout_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(identifier: str) -> str:
        return (identifier or "").strip().lower()

    def check(self, identifier: str) -> None:
        """Raise AuthError if this account is currently locked out."""
        key, now = self._key(identifier), time.monotonic()
        with self._lock:
            until = self._locked_until.get(key)
            if until and now < until:
                minutes = max(1, int((until - now) // 60) + 1)
                raise AuthError(f"Too many failed attempts. Try again in {minutes} minute(s).")
            if until:
                del self._locked_until[key]

    def record_failure(self, identifier: str) -> None:
        key, now = self._key(identifier), time.monotonic()
        with self._lock:
            hits = self._failures[key]
            hits.append(now)
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_failures:
                self._locked_until[key] = now + self.lockout
                hits.clear()

    def record_success(self, identifier: str) -> None:
        key = self._key(identifier)
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)


class RedisLoginThrottle:
    """
    The same limiter with its counters in Redis, so the limit holds across every API/app instance.

    Uses a fixed window (first failure starts the clock) rather than a sliding one. If Redis is unreachable it
    falls back to the per-process limiter: sign-in must never depend on Redis being up, and locking people out
    because of an outage would be worse than a per-instance limit.
    """

    def __init__(self, client, name: str, max_failures: int = 5, window_seconds: int = 900, lockout_seconds: int = 900):
        self._r = client
        self._prefix = f"throttle:{name}:"
        self.max_failures, self.window, self.lockout = max_failures, window_seconds, lockout_seconds
        self._local = LoginThrottle(max_failures, window_seconds, lockout_seconds)

    def _keys(self, identifier: str) -> tuple[str, str]:
        key = LoginThrottle._key(identifier)
        return f"{self._prefix}fail:{key}", f"{self._prefix}lock:{key}"

    def check(self, identifier: str) -> None:
        _, lock = self._keys(identifier)
        try:
            ttl = self._r.ttl(lock)
        except Exception:  # noqa: BLE001 - Redis down: use the local limiter
            return self._local.check(identifier)
        if ttl and ttl > 0:
            raise AuthError(f"Too many failed attempts. Try again in {max(1, ttl // 60 + 1)} minute(s).")

    def record_failure(self, identifier: str) -> None:
        fail, lock = self._keys(identifier)
        try:
            count = self._r.incr(fail)
            if count == 1:
                self._r.expire(fail, self.window)
            if count >= self.max_failures:
                self._r.set(lock, 1, ex=self.lockout)
                self._r.delete(fail)
        except Exception:  # noqa: BLE001
            self._local.record_failure(identifier)

    def record_success(self, identifier: str) -> None:
        fail, lock = self._keys(identifier)
        try:
            self._r.delete(fail, lock)
        except Exception:  # noqa: BLE001
            self._local.record_success(identifier)


def make_login_throttle(name: str):
    """A Redis-backed throttle when REDIS_URL is set, otherwise the per-process one."""
    from backend.core.config import get_settings

    url = get_settings().redis_url
    if not url:
        return LoginThrottle()
    import redis

    return RedisLoginThrottle(redis.from_url(url, socket_timeout=1, socket_connect_timeout=1), name)


MIN_PASSWORD_LENGTH = 10
_COMMON_PASSWORDS = {"password123", "1234567890", "qwertyuiop", "administrator", "changeme123"}


def validate_password(password: str) -> None:
    """Reject weak passwords chosen by a person (generated ones are always long and random)."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(set(password)) < 5:
        raise AuthError("Password is too repetitive.")
    if password.lower() in _COMMON_PASSWORDS:
        raise AuthError("Password is too common.")
