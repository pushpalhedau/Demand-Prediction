import pytest
from sqlalchemy import Boolean, Date, Float, Integer, Text

from database import models
from schema.catalog import TABLES

_MODEL = {"sales": models.Sale, "dealers": models.Dealer, "vehicles": models.Vehicle,
          "customers": models.Customer, "inventory": models.Inventory,
          "external_factors": models.ExternalFactor}
_TYPE = {"str": Text, "int": Integer, "float": Float, "bool": Boolean, "date": Date}


@pytest.mark.parametrize("table", list(TABLES))
def test_every_catalog_field_is_a_model_column_of_the_same_kind(table):
    cols = {c.name: c for c in _MODEL[table].__table__.columns}
    for f in TABLES[table]:
        if f.derived:
            continue
        assert f.name in cols, f"{table}.{f.name} is in the catalog but not in the model"
        assert isinstance(cols[f.name].type, _TYPE[f.kind]), f"{table}.{f.name}: {f.kind} vs {cols[f.name].type}"


@pytest.mark.parametrize("table", list(TABLES))
def test_every_model_column_is_reachable_from_the_catalog(table):
    known = {f.name for f in TABLES[table]}
    housekeeping = {"tenant_id", "extras", "id"}
    orphans = [c.name for c in _MODEL[table].__table__.columns if c.name not in known | housekeeping]
    assert not orphans, f"{table} columns that an upload can never populate: {orphans}"


@pytest.mark.parametrize("table", list(TABLES))
def test_no_currency_or_market_in_a_column_name(table):
    bad = [c.name for c in _MODEL[table].__table__.columns
           if any(tok in c.name.split("_") for tok in ("eur", "aed", "gbp", "inr", "vat"))]
    assert not bad, bad
