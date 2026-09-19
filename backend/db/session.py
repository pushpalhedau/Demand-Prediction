"""Unit-of-work helpers: a tenant-scoped session that is always closed, never leaked to callers."""
from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from backend.db.connection import get_db_session

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def session_scope() -> Iterator[Session]:
    """A tenant-scoped session (RLS enforced) for one unit of work. Rolls back on error, always closes."""
    session = get_db_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def with_session(fn: F) -> F:
    """Call `fn(session, *args)` inside a session_scope(); callers pass only the remaining arguments."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with session_scope() as session:
            return fn(session, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
