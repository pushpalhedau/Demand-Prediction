import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import generate_us_data as us  # noqa: E402
from dataset_export import canonicalize  # noqa: E402

from backend.ingestion.catalog import LOAD_ORDER, TABLES  # noqa: E402
from backend.ingestion.mapping import propose_mapping  # noqa: E402
from backend.ingestion.pipeline import transform_table  # noqa: E402


@pytest.fixture(scope="module")
def america(tmp_path_factory):
    folder = tmp_path_factory.mktemp("us")
    tables = us.generate_dataset(str(folder), seed=7, n_customers=1500, n_sales=3000, n_rooftops=24, n_trims=2)
    return {name: canonicalize(name, df)[0] for name, df in tables.items()}


def test_every_column_maps_with_exact_confidence(america):
    for table, df in america.items():
        proposal = propose_mapping(table, list(df.columns))
        assert not proposal.unmapped, (table, proposal.unmapped)
        assert all(c.confidence == "exact" for c in proposal.choices.values()), table
        assert not proposal.missing_required


def test_every_row_loads_through_the_platform_pipeline(america):
    for table in LOAD_ORDER:
        raw = america[table].astype(str).replace({"<NA>": None, "nan": None, "None": None})
        proposal = propose_mapping(table, list(raw.columns))
        _, report = transform_table(table, raw, proposal.to_mapping(), {"distance": "km"}, False, ".")
        assert report["rows_out"] == report["rows_in"] and not report["coercion_failures"], table


def test_columns_follow_the_catalog_order_and_use_no_currency_names(america):
    for table, df in america.items():
        expected = [f.name for f in TABLES[table] if f.name in df.columns]
        assert list(df.columns) == expected
        assert not any(c.endswith(("_usd", "_eur", "_aed")) for c in df.columns if c != "crude_oil_price_usd")


def test_annual_volume_follows_the_real_us_market(america):
    real = pd.read_csv(us.PUBLIC / "TOTALNSA.csv", index_col=0, parse_dates=True).iloc[:, 0]
    demo = pd.to_datetime(america["sales"]["sale_date"]).dt.year.value_counts().sort_index()
    real_year = real.groupby(real.index.year).sum()
    for year in range(2020, 2026):
        demo_change = demo[year] / demo[year - 1] - 1
        real_change = real_year[year] / real_year[year - 1] - 1
        assert abs(demo_change - real_change) < 0.06, year        # small sample: loose bound


def test_sales_are_internally_consistent(america):
    s = america["sales"]
    assert (s["selling_price"] <= s["base_price"]).all()
    assert (s["total_revenue_incl_tax"] >= s["total_revenue_excl_tax"]).all()
    assert s["tax_amount"].between(0, s["selling_price"] * 0.1).all()
    leased = s[s["financing_type"] == "Lease"]
    assert leased["lease_maturity_date"].notna().all() and (leased["lease_monthly_payment"] > 0).all()
    assert s[s["financing_type"] != "Lease"]["lease_term_months"].isna().all()
    assert set(s["customer_id"]) <= set(america["customers"]["customer_id"])
    assert set(s["dealer_id"]) <= set(america["dealers"]["dealer_id"])
    assert set(s["vehicle_id"]) <= set(america["vehicles"]["vehicle_id"])


def test_customers_look_like_the_us_market(america):
    c = america["customers"]
    assert 690 <= c["credit_score"].mean() <= 740 and c["credit_score"].between(300, 850).all()
    assert 60000 <= c["annual_income"].median() <= 100000


def test_units_are_metric(america):
    v = america["vehicles"]
    ice = v[v["fuel_type"].isin(["Petrol", "Diesel", "Hybrid"])]
    assert ice["consumption_l_per_100km"].between(3.5, 20).all()          # a US 15 mpg pickup is ~15.7 l/100km
    assert np.isclose(v["consumption_l_per_100km"].dropna().min(), 235.2146 / 57, atol=0.4)   # Prius, 57 mpg
