"""Logging setup shared by every entry point (web apps, worker, CLI)."""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Idempotent. Logs go to stderr so containers collect them; never log secrets or personal data."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    from backend.core.config import get_settings

    logging.basicConfig(level=(level or get_settings().log_level), format=_FORMAT, stream=sys.stderr)
    # Third-party loggers that would otherwise echo request URLs / payloads at DEBUG.
    for noisy in ("urllib3", "httpx", "prophet", "cmdstanpy", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
