import pytest

from backend.ingestion.mapping import propose_mapping


def test_mileage_kmpl_is_not_imperial():
    p = propose_mapping("vehicles", ["vehicle_id", "brand", "mileage_kmpl", "horsepower"])
    assert p.choices["consumption_l_per_100km"].transform == ("inv", 100.0)
    assert not p.imperial_hint


def test_mpg_and_range_miles_are_imperial_and_converted():
    p = propose_mapping("vehicles", ["vehicle_id", "mpg", "range_miles"])
    assert p.imperial_hint
    assert p.choices["consumption_l_per_100km"].transform[0] == "inv"
    assert p.choices["range_km"].transform == ("mul", pytest.approx(1.609344))


@pytest.mark.parametrize("col", ["price_eur", "price_aed", "price_usd", "Price"])
def test_currency_suffix_is_ignored(col):
    assert propose_mapping("vehicles", ["vehicle_id", col]).choices["price"].source == col


@pytest.mark.parametrize("col", ["state", "emirate", "Bundesland", "province"])
def test_region_synonyms(col):
    assert propose_mapping("dealers", ["dealer_id", col]).choices["region"].source == col


def test_fuzzy_match_is_proposed_but_not_auto_applied():
    p = propose_mapping("sales", ["sale_date", "selling_pric", "units_sold"])
    assert p.choices["selling_price"].confidence == "fuzzy"
    assert "selling_price" not in p.to_mapping()["columns"]
    assert "selling_price" in p.to_mapping(accept_fuzzy=True)["columns"]


def test_unknown_columns_go_to_extras_and_missing_required_is_reported():
    p = propose_mapping("sales", ["ramadan_bonus", "colour"])
    assert p.missing_required == ["sale_date"]
    assert set(p.unmapped) == {"ramadan_bonus", "colour"}


def test_one_source_column_feeds_one_field():
    p = propose_mapping("sales", ["sale_date", "price"])
    fed = [f for f, c in p.choices.items() if c.source == "price"]
    assert fed == ["selling_price"]
