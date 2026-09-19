"""Workspace-level reads: what data the tenant has, and the values for the global filters."""
from backend.db.session import with_session
from backend.repositories import catalog
from backend.tenancy.capabilities import get_capabilities, tab_available

__all__ = ["cities_in_region", "filter_options", "get_capabilities", "tab_available"]


@with_session
def filter_options(session) -> dict:
    return catalog.get_unique_filter_options(session)


@with_session
def cities_in_region(session, region: str) -> list[str]:
    return catalog.get_cities_in_region(session, region)
