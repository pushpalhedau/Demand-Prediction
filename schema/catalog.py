"""
Canonical (market-neutral) field catalog: the single source of truth the
upload wizard, auto-detection, validation and loader are all driven by.

Everything is stored in neutral names and metric units. Currency is NOT part of
a column name: it lives in the tenant's config. A source column such as
`price_eur`, `price_aed` or `price_usd` all map to `price`.

Source columns with no canonical home are kept per-row in the JSONB `extras`
column, so nothing a customer uploads is lost.
"""
import re
from dataclasses import dataclass

CURRENCY_TOKENS = frozenset({"eur", "aed", "usd", "gbp", "inr", "cad", "aud", "sar", "chf", "jpy", "cny"})

# Transform ops applied to the numeric source value: ("mul", k) -> v*k ; ("inv", k) -> k/v
MI_TO_KM = 1.609344
SQFT_TO_SQM = 0.09290304
HP_TO_KW = 0.7456999
PS_TO_KW = 0.7354988
GAL_TO_L = 3.785411784
L100_FROM_MPG = 235.214583    # l/100km = 235.2146 / mpg
L100_FROM_KMPL = 100.0        # l/100km = 100 / (km/l)


def norm(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", str(name).strip().lower()).strip("_")


def strip_currency(n: str) -> str:
    return "_".join(p for p in n.split("_") if p not in CURRENCY_TOKENS)


@dataclass(frozen=True)
class Field:
    name: str
    kind: str                      # str | int | float | bool | date
    required: bool = False
    default: object = None         # fills NULLs in a MAPPED column; None keeps NULL; "median" = column median
    aliases: tuple = ()            # synonyms, identity transform
    converted: tuple = ()          # ((alias, (op, k)), ...): the source name implies a unit conversion
    dim: str = None                # "distance": unit is not in the name, so the upload declares km or mi
    derived: bool = False          # read from the file to build another table; not stored on this one


def F(name, kind, required=False, default=None, aliases=(), converted=(), dim=None, derived=False):
    return Field(name, kind, required, default, tuple(aliases), tuple(converted), dim, derived)


_REGION = ("state", "emirate", "province", "county", "bundesland", "territory")
_CITY = ("area", "town", "locality")
_POSTAL = ("zip_code", "zip", "po_box", "plz", "postcode", "post_code")

CUSTOMERS = (
    F("customer_id", "str", required=True, aliases=("cust_id", "client_id")),
    F("name", "str", default="Unknown Customer", aliases=("customer_name", "full_name")),
    F("age", "int", default="median"),
    F("gender", "str", default="Other"),
    F("nationality", "str", default="Unknown"),
    F("customer_type", "str"),
    F("region", "str", aliases=_REGION),
    F("city", "str", aliases=_CITY),
    F("postal_code", "str", aliases=_POSTAL),
    F("occupation", "str"),
    F("income_bracket", "str", aliases=("annual_income_bracket", "monthly_income_bracket")),
    F("annual_income", "float", default="median",
      aliases=("estimated_annual_income", "annual_income_estimate"),
      converted=(("estimated_monthly_income", ("mul", 12)), ("monthly_income", ("mul", 12)))),
    F("credit_score", "int", default="median", aliases=("schufa_score", "fico_score", "credit_rating")),
    F("years_at_address", "int", default="median", aliases=("years_in_uae", "years_at_residence", "years_in_country")),
    F("number_of_past_purchases", "int", default=0, aliases=("past_purchases", "prior_purchases")),
    F("preferred_fuel_type", "str"),
    F("preferred_vehicle_category", "str"),
    F("customer_segment", "str", aliases=("segment",)),
    F("loyalty_score", "float", default=50.0),
    F("marketing_response_score", "float", default=5.0),
    F("lead_source", "str"),
    F("email_opt_in", "bool", default=False),
    F("test_drive_taken", "bool", default=False),
    F("financing_preferred", "bool", default=False, aliases=("emi_preferred",)),
    F("down_payment_capacity", "float", default=0, aliases=("down_payment",)),
    F("registration_date", "date", aliases=("customer_since",)),
    F("last_activity_date", "date"),
    F("churn_risk_score", "float", default=0.5),
)

VEHICLES = (
    F("vehicle_id", "str", required=True, aliases=("vehicle_code", "sku", "model_id")),
    F("brand", "str", default="Unknown", aliases=("make", "manufacturer")),
    F("model", "str", default="Unknown", aliases=("model_name",)),
    F("variant", "str", aliases=("trim", "version")),
    F("category", "str", aliases=("vehicle_category", "body_type", "body_style", "segment")),
    F("fuel_type", "str", aliases=("fuel", "powertrain")),
    F("price", "float", default=0, aliases=("list_price", "msrp", "base_price", "listenpreis")),
    F("engine_cc", "int", aliases=("displacement_cc", "engine_size_cc")),
    F("power_kw", "int", converted=(("horsepower", ("mul", HP_TO_KW)), ("hp", ("mul", HP_TO_KW)),
                                    ("ps", ("mul", PS_TO_KW)), ("power_ps", ("mul", PS_TO_KW)))),
    F("consumption_l_per_100km", "float",
      aliases=("fuel_consumption_l_per_100km",),
      converted=(("mileage_kmpl", ("inv", L100_FROM_KMPL)), ("km_per_litre", ("inv", L100_FROM_KMPL)),
                 ("kmpl", ("inv", L100_FROM_KMPL)), ("mpg", ("inv", L100_FROM_MPG)))),
    F("consumption_kwh_per_100km", "float", aliases=("energy_consumption_kwh_per_100km",)),
    F("range_km", "int", aliases=("electric_range_km", "wltp_range_km"),
      converted=(("range_miles", ("mul", MI_TO_KM)), ("range_mi", ("mul", MI_TO_KM)))),
    F("co2_g_per_km", "int", aliases=("co2_emissions_g_km",)),
    F("origin", "str", aliases=("country_of_origin",)),
    F("seating_capacity", "int", default=5, aliases=("seats",)),
    F("transmission", "str"),
    F("drive_type", "str", aliases=("drivetrain",)),
    F("body_color_options", "int", default=1),
    F("safety_rating", "int"),
    F("launch_year", "int"),
    F("is_active", "bool", default=True, aliases=("active",)),
    F("warranty_years", "int"),
    F("service_contract_available", "bool", default=False),
    F("residual_value_36mo", "float"),
)

DEALERS = (
    F("dealer_id", "str", required=True, aliases=("store_id", "rooftop_id", "location_id")),
    F("dealer_name", "str", default="Unknown Dealer", aliases=("store_name", "rooftop", "dealership", "dealer")),
    F("brand", "str", default="Unknown", aliases=("make", "franchise")),
    F("region", "str", aliases=_REGION),
    F("city", "str", aliases=_CITY),
    F("address", "str"),
    F("postal_code", "str", aliases=_POSTAL),
    F("tier", "str"),
    F("established_year", "int"),
    F("monthly_capacity", "int", default="median"),
    F("showroom_area_sqm", "int", default="median", converted=(("showroom_area_sqft", ("mul", SQFT_TO_SQM)),)),
    F("service_center", "bool", default=False),
    F("ev_charging_station", "bool", default=False),
    F("num_salespeople", "int", default="median"),
    F("annual_target_units", "int", default="median"),
    F("performance_score", "float", default="median"),
    F("google_rating", "float", default="median"),
    F("latitude", "float", aliases=("lat",)),
    F("longitude", "float", aliases=("lon", "lng", "long")),
)

SALES = (
    F("sale_id", "str", aliases=("transaction_id", "order_id", "deal_id", "invoice_id")),
    F("sale_date", "date", required=True, aliases=("date", "transaction_date", "order_date", "invoice_date")),
    F("year", "int"),
    F("month", "int"),
    F("quarter", "str"),
    F("day_of_week", "str"),
    F("season_period", "str", aliases=("festival_period", "holiday_period", "season")),
    F("customer_id", "str", aliases=("cust_id", "client_id")),
    F("dealer_id", "str", aliases=("store_id", "rooftop_id", "location_id")),
    F("dealer_name", "str", derived=True, aliases=("store_name", "rooftop", "dealership", "dealer")),
    F("vehicle_id", "str", aliases=("sku", "model_id")),
    F("brand", "str", default="Unknown", aliases=("make", "manufacturer")),
    F("model", "str", default="Unknown", aliases=("model_name",)),
    F("vehicle_category", "str", aliases=("category", "body_type", "segment")),
    F("fuel_type", "str", aliases=("fuel",)),
    F("region", "str", aliases=_REGION),
    F("city", "str", aliases=_CITY),
    F("customer_type", "str"),
    F("is_fleet", "bool", default=False),
    F("base_price", "float", default=0, aliases=("list_price", "msrp")),
    F("discount_pct", "float", default=0.0, aliases=("discount_percent", "discount")),
    F("selling_price", "float", aliases=("sale_price", "transaction_price", "price", "net_price")),
    F("tax_amount", "float", default=0, aliases=("vat_amount", "sales_tax_amount", "tax", "vat")),
    F("accessories_revenue", "float", default=0),
    F("insurance_revenue", "float", default=0),
    F("extended_warranty", "float", default=0),
    F("total_revenue_excl_tax", "float", aliases=("total_revenue_excl_vat", "revenue_excl_tax", "net_revenue")),
    F("total_revenue_incl_tax", "float", aliases=("total_revenue_incl_vat", "revenue_incl_tax", "gross_revenue", "total_revenue")),
    F("financing_type", "str", default="Cash", aliases=("payment_type", "payment_method")),
    F("loan_amount", "float", default=0),
    F("units_sold", "int", default=1, aliases=("units", "quantity", "qty")),
    F("test_drive_converted", "bool", default=False),
    F("lead_to_close_days", "int", default=0),
    F("salesperson_id", "str", aliases=("sales_rep_id", "salesperson")),
    F("marketing_channel", "str", aliases=("channel",)),
    F("season_multiplier", "float", default=1.0),
    F("lease_term_months", "int"),
    F("lease_maturity_date", "date"),
    F("residual_value_pct", "float"),
    F("residual_value", "float"),
    F("contract_mileage_allowance", "int", dim="distance"),
    F("lease_monthly_payment", "float"),
    F("trade_in_flag", "bool", default=False, aliases=("trade_in",)),
    F("trade_in_brand", "str"),
    F("trade_in_model", "str"),
    F("trade_in_year", "int"),
    F("trade_in_mileage", "int", dim="distance"),
    F("trade_in_appraised_value", "float"),
    F("trade_in_allowance", "float"),
    F("trade_in_over_allowance", "float"),
    F("trade_bonus", "float", default=0),
)

INVENTORY = (
    F("inventory_id", "str", aliases=("stock_id", "snapshot_id")),
    F("record_date", "date", required=True, aliases=("date", "snapshot_date", "stock_date")),
    F("dealer_id", "str", aliases=("store_id", "rooftop_id", "location_id")),
    F("vehicle_id", "str", aliases=("sku", "model_id")),
    F("brand", "str", default="Unknown", aliases=("make",)),
    F("model", "str", default="Unknown"),
    F("vehicle_category", "str", aliases=("category", "body_type")),
    F("fuel_type", "str", aliases=("fuel",)),
    F("region", "str", aliases=_REGION),
    F("city", "str", aliases=_CITY),
    F("current_stock", "int", default=0, aliases=("stock", "units_in_stock", "on_hand")),
    F("demand_forecast_30d", "int", default=0),
    F("reorder_point", "int", default=0),
    F("days_in_stock", "int", default=0, aliases=("days_on_lot", "age_days")),
    F("stockout_flag", "bool"),
    F("overstock_flag", "bool", default=False),
    F("reorder_needed", "bool", default=False),
    F("stockout_risk_score", "float", default=0.0),
    F("overstock_risk_score", "float", default=0.0),
    F("holding_cost_per_day", "float", default=0.0),
    F("estimated_holding_cost", "float", default=0.0),
    F("units_sold_last_30d", "int", default=0),
    F("units_ordered", "int", default=0),
    F("transit_stock", "int", default=0, aliases=("in_transit",)),
    F("origin_hub", "str", aliases=("port_of_entry", "origin_port", "plant")),
    F("warehouse_zone", "str"),
    F("last_replenishment_date", "date"),
    F("supplier_lead_time_days", "int", default=21, aliases=("lead_time_days",)),
    F("customs_cleared", "bool"),
)

EXTERNAL_FACTORS = (
    F("date", "date", required=True, aliases=("period", "record_date")),
    F("year", "int"),
    F("month", "int"),
    F("quarter", "str"),
    F("region", "str", aliases=_REGION),
    F("petrol_price_per_litre", "float", default="median",
      aliases=("super_e10_price_per_litre", "petrol_95_price_per_litre", "petrol_price", "gasoline_price_per_litre"),
      converted=(("gasoline_regular_usd_per_gallon", ("mul", 1 / GAL_TO_L)),
                 ("gasoline_regular_per_gallon", ("mul", 1 / GAL_TO_L)))),
    F("diesel_price_per_litre", "float", default="median",
      converted=(("diesel_usd_per_gallon", ("mul", 1 / GAL_TO_L)), ("diesel_per_gallon", ("mul", 1 / GAL_TO_L)))),
    F("crude_oil_price_usd", "float", default="median", aliases=("wti_crude_price_usd", "brent_price_usd")),
    F("policy_rate_pct", "float", default="median",
      aliases=("ecb_rate_pct", "cbuae_rate_pct", "us_fed_rate_pct", "central_bank_rate_pct", "base_rate_pct")),
    F("auto_loan_apr_pct", "float", default="median"),
    F("incentive_pct_of_atp", "float", default="median"),
    F("inventory_days_supply", "float", default="median"),
    F("gdp_growth_pct", "float", default="median"),
    F("cpi_inflation_pct", "float", default="median"),
    F("consumer_confidence_index", "float", default="median"),
    F("business_climate_index", "float", default="median", aliases=("ifo_business_climate",)),
    F("house_price_index", "float", default="median",
      aliases=("de_house_price_index", "dubai_re_price_index", "home_price_index", "property_price_index")),
    F("luxury_demand_index", "float", default="median"),
    F("unemployment_rate_pct", "float", default="median"),
    F("population_millions", "float", default="median"),
    F("new_model_launches", "int", default=0),
    F("tax_rate_pct", "float", aliases=("vat_rate_pct", "avg_sales_tax_pct", "sales_tax_pct")),
    F("ev_charging_points", "int", default=0,
      aliases=("ev_charging_points_de", "ev_charging_stations", "ev_charging_stations_uae")),
    F("quarter_end_month", "int", default=0),
    F("year_end_month", "int", default=0),
)

TABLES = {
    "sales": SALES,
    "dealers": DEALERS,
    "vehicles": VEHICLES,
    "customers": CUSTOMERS,
    "inventory": INVENTORY,
    "external_factors": EXTERNAL_FACTORS,
}

# Load parents before children; sales is the only table a tenant must supply.
LOAD_ORDER = ("vehicles", "dealers", "customers", "external_factors", "sales", "inventory")
REQUIRED_TABLES = ("sales",)

# Natural key used to de-duplicate a file; external_factors has no id column.
NATURAL_KEY = {
    "sales": ("sale_id",), "dealers": ("dealer_id",), "vehicles": ("vehicle_id",),
    "customers": ("customer_id",), "inventory": ("inventory_id",), "external_factors": ("date", "region"),
}

# Which tabs a table unlocks (used to hide tabs a tenant has no data for).
UNLOCKS = {
    "customers": "tab.customers",
    "inventory": "tab.inventory",
}


def fields_of(table: str) -> tuple:
    return TABLES[table]


def field_map(table: str) -> dict:
    return {f.name: f for f in TABLES[table]}
