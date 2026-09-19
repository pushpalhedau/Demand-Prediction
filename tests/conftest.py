"""
Shared test configuration.

Tests are grouped by what they need to run:
  unit         nothing external; fast
  integration  a Postgres database   (docker compose up -d db)
  e2e          the running services  (docker compose up -d db auth [redis worker])

    pytest -m unit                 quick check
    pytest -m "unit or integration"
    pytest                         everything (tests skip themselves when a service they need is down)
"""
from pathlib import Path

import pytest

from backend.core.request_context import clear_request

_GROUPS = ("unit", "integration", "e2e")


def pytest_collection_modifyitems(items):
    for item in items:
        parts = Path(str(item.fspath)).parts
        for group in _GROUPS:
            if group in parts:
                item.add_marker(getattr(pytest.mark, group))


@pytest.fixture(autouse=True)
def _no_scope_leaks_between_tests():
    """Request scope lives in ContextVars on the test thread; make sure no test inherits another's tenant."""
    clear_request()
    yield
    clear_request()
