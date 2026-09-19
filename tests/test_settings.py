import pytest

from tenancy.settings import InvalidSetting, validate_config


def test_ordinary_settings_pass():
    ok = validate_config({"currency": "GBP", "currency_symbol": "£", "language": "en",
                          "region_label": "County", "country_name": "United Kingdom", "news_gl": "GB"})
    assert ok["currency"] == "GBP" and ok["currency_symbol"] == "£"


@pytest.mark.parametrize("key,value", [
    ("currency_symbol", "<img src=x onerror=alert(1)>"),
    ("currency_symbol", "\"><script>"),
    ("region_label", "<b>State</b>"),
    ("region_label", "State\nLabel"),
    ("country_name", "Evil<script>"),
    ("currency", "usd"),
    ("language", "fr"),
    ("news_gl", "USA"),
])
def test_values_that_could_carry_markup_are_rejected(key, value):
    with pytest.raises(InvalidSetting):
        validate_config({key: value})


def test_keys_outside_the_whitelist_are_dropped_not_stored():
    assert validate_config({"status": "active", "name": "x", "currency": "EUR"}) == {"currency": "EUR"}
