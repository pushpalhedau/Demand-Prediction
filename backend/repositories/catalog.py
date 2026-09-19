"""Reference data for the filter controls."""
from sqlalchemy.orm import Session

from backend.db.models import Sale


def get_unique_filter_options(session: Session) -> dict:
    """Distinct regions, cities, categories, fuel types, brands and years present in the tenant's sales."""
    def distinct(column) -> list:
        return sorted(v[0] for v in session.query(column).distinct().all() if v[0])

    return {
        "regions": distinct(Sale.region),
        "cities": distinct(Sale.city),
        "categories": distinct(Sale.vehicle_category),
        "fuel_types": distinct(Sale.fuel_type),
        "brands": distinct(Sale.brand),
        "years": distinct(Sale.year),
    }


def get_cities_in_region(session: Session, region: str) -> list[str]:
    rows = session.query(Sale.city).filter(Sale.region == region).distinct().all()
    return sorted(c[0] for c in rows if c[0])
