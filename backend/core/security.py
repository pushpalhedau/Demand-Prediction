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
