"""Shared filter helpers: turn the dashboard's filter dict into SQLAlchemy predicates."""

from backend.db.models import Dealer, Inventory, Sale


def shift_years(d, n):
    try:
        return d.replace(year=d.year - n)
    except ValueError:            # Feb 29 → Feb 28
        return d.replace(year=d.year - n, day=28)


def apply_dealer_scope(query, filters: dict):
    """Apply the location/brand slice of the global filters to a Dealer query."""
    if not filters:
        return query
    if filters.get("region"):
        query = query.filter(Dealer.region == filters["region"])
    if filters.get("city"):
        query = query.filter(Dealer.city == filters["city"])
    if filters.get("brand"):
        query = query.filter(Dealer.brand == filters["brand"])
    return query


def apply_sale_filters(query, filters: dict = None):
    """
    Helper to apply global filters to sales-related queries.
    """
    if not filters:
        return query

    if filters.get("region"):
        query = query.filter(Sale.region == filters["region"])
    if filters.get("city"):
        query = query.filter(Sale.city == filters["city"])

    if filters.get("vehicle_category"):
        query = query.filter(Sale.vehicle_category == filters["vehicle_category"])
    if filters.get("fuel_type"):
        query = query.filter(Sale.fuel_type == filters["fuel_type"])
    if filters.get("brand"):
        query = query.filter(Sale.brand == filters["brand"])
    if filters.get("financing_type"):
        query = query.filter(Sale.financing_type == filters["financing_type"])

    # Apply date filters
    if filters.get("start_date"):
        query = query.filter(Sale.sale_date >= filters["start_date"])
    if filters.get("end_date"):
        query = query.filter(Sale.sale_date <= filters["end_date"])

    return query


def apply_inventory_filters(query, filters: dict = None):
    """Apply the global sidebar filters to an inventory-rooted query."""
    if not filters:
        return query
    if filters.get("region"):
        query = query.filter(Inventory.region == filters["region"])
    if filters.get("city"):
        query = query.filter(Inventory.city == filters["city"])
    if filters.get("brand"):
        query = query.filter(Inventory.brand == filters["brand"])
    if filters.get("vehicle_category"):
        query = query.filter(Inventory.vehicle_category == filters["vehicle_category"])
    if filters.get("fuel_type"):
        query = query.filter(Inventory.fuel_type == filters["fuel_type"])
    return query
