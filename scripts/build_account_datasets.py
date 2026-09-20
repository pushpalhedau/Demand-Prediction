"""
Build ready-to-upload CSV sets for the three demo accounts into Accounts-Datasets/{Germany,UAE,America}/.

    python scripts/build_account_datasets.py                 # all three, full size
    python scripts/build_account_datasets.py --only America  # one account
    python scripts/build_account_datasets.py --sales 4000 --customers 3000 --out some/dir   # small smoke build

Each folder gets the six standard files in the platform's exact field names (metric, currency-free), plus a README.txt
with the account settings, upload steps and an honest statement of what is real and what is modelled. Every file is then
checked with the platform's own import pipeline: all columns must map with "exact" confidence and every row must load.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT)]

import generate_de_data  # noqa: E402
import generate_uae_data  # noqa: E402
import generate_us_data  # noqa: E402
from dataset_export import canonicalize  # noqa: E402

from backend.ingestion.catalog import LOAD_ORDER  # noqa: E402
from backend.ingestion.mapping import propose_mapping  # noqa: E402
from backend.ingestion.pipeline import transform_table  # noqa: E402

PUBLIC = ROOT / "data" / "public"


def _fred_monthly(series_id: str, how: str = "last") -> pd.Series:
    df = pd.read_csv(PUBLIC / f"fred_{series_id}.csv")
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(), index=pd.to_datetime(df.iloc[:, 0])).dropna()
    monthly = s.resample("MS").mean() if how == "mean" else s.resample("MS").last()
    return monthly.dropna()


def _apply(df: pd.DataFrame, column: str, series: pd.Series, digits: int = 2) -> None:
    """Overwrite an external-factors column with a real monthly series (latest published value carried forward)."""
    months = pd.to_datetime(df["date"]).dt.to_period("M").dt.to_timestamp()
    aligned = series.reindex(pd.date_range(min(series.index.min(), months.min()), months.max(), freq="MS")).ffill()
    df[column] = months.map(aligned).round(digits).to_numpy()


def _germany_real_macro(ext: pd.DataFrame) -> pd.DataFrame:
    """Replace the hand-set German macro columns with the published series (ECB, Eurostat, Destatis via FRED)."""
    ext = ext.copy()
    ecb = _fred_monthly("ECBMRRFR")
    _apply(ext, "ecb_rate_pct", ecb)
    ext["auto_loan_apr_pct"] = (ext["ecb_rate_pct"] + 3.0).round(2)      # modelled: policy rate plus a typical new-car spread
    _apply(ext, "crude_oil_price_usd", _fred_monthly("MCOILBRENTEU", "mean"))
    hicp = _fred_monthly("CP0000DEM086NEST")
    _apply(ext, "cpi_inflation_pct", (hicp.pct_change(12) * 100).dropna())
    _apply(ext, "unemployment_rate_pct", _fred_monthly("LRHUTTTTDEM156S"))
    gdp = _fred_monthly("CLVMNACSCAB1GQDE")
    _apply(ext, "gdp_growth_pct", (gdp.pct_change(4) * 100).dropna())          # quarterly series: 4 quarters back
    return ext


def _uae_real_macro(ext: pd.DataFrame) -> pd.DataFrame:
    ext = ext.copy()
    _apply(ext, "crude_oil_price_usd", _fred_monthly("MCOILBRENTEU", "mean"))
    return ext


MARKETS = {
    "Germany": {
        "slug": "germany-demo", "currency": "EUR (euro)", "region": "Bundesland", "language": "German (de)",
        "distance": "km", "generator": generate_de_data,
        "kwargs": dict(seed=42, n_customers=70000, n_rooftops=24, n_sales=100000, n_trims=2),
        "post_external": _germany_real_macro,
        "real": [
            "Yearly sales volume follows the official KBA / Destatis new-car registrations (2020 -19.1%, 2021 -10.1%, 2022 +1.1%, 2023 +7.3%, 2024 -1.0%, 2025 +1.4%).",
            "external_factors: ECB main refinancing rate, Brent crude, HICP inflation, unemployment (ILO) and GDP growth are the published series (FRED: ECB, Eurostat, Destatis).",
            "German VAT (19%, 16% in H2 2020), the Umweltbonus EV-subsidy timeline and the 2022 fuel-tax cut are real events.",
        ],
        "modelled": [
            "Every individual sale, customer, store and stock position, model specs and prices (approximate German list prices).",
            "external_factors: pump prices, electricity price, consumer confidence, ifo, house prices and incentive spend are hand-set approximations of the real paths, not downloaded series.",
        ],
    },
    "UAE": {
        "slug": "uae-demo", "currency": "AED (dirham)", "region": "Emirate", "language": "English (en)",
        "distance": "km", "generator": generate_uae_data,
        "kwargs": dict(seed=42, n_customers=70000, n_rooftops=24, n_sales=100000, n_trims=2),
        "post_external": _uae_real_macro,
        "real": [
            "Sales volume follows the UAE new-car market for 2019-2022 (2020 -30.5%, 2021 +28%, 2022 +2.7%; one aggregator, Statista).",
            "external_factors: Brent crude is the published series. Ramadan and Eid dates, National Day, DSF are real calendar events.",
        ],
        "modelled": [
            "Sales volume for 2023 onward is a conservative reading: published sources disagree (2024 is quoted as both ~269k and 300k+). Replace with verified figures if you have them.",
            "Every individual sale, customer, store and stock position, model specs and prices.",
            "external_factors other than Brent (rates, fuel, GDP, CPI, tourism, house prices, incentives) are hand-set approximations of the real paths.",
        ],
    },
    "America": {
        "slug": "na-demo", "currency": "USD (US dollar)", "region": "State", "language": "English (en)",
        "distance": "km (all mileage columns are already converted; do NOT choose miles)", "generator": generate_us_data,
        "kwargs": dict(seed=42, n_customers=70000, n_sales=100000, n_rooftops=24, n_trims=4),
        "post_external": None,
        "real": [
            "Monthly sales volume follows the real US new light-vehicle sales series (BEA), so 2020, the 2021-22 chip shortage and the recovery land in the right months.",
            "external_factors: gasoline, diesel and crude prices, fed funds rate, 48-month new-car loan rate, CPI inflation, unemployment, GDP growth, consumer sentiment, house prices and dealer inventory-to-sales (as days' supply) are published series (BLS, BEA, Census, Federal Reserve, EIA, Univ. of Michigan via FRED).",
            "List prices follow the CPI for new vehicles; trade-in values follow the CPI for used vehicles (the 2021-22 spike is in the appraisals).",
        ],
        "modelled": [
            "Every individual sale, customer, store and stock position; model specs and prices (approximate 2025-26 US figures).",
            "Incentive spend (% of transaction price) and the state vehicle-tax rates are approximate.",
            "State gas-price differences are typical regional offsets, not month-by-month data.",
        ],
    },
}

REQUIRED_NOTE = ("These files contain SYNTHETIC records calibrated to real market data. No real customer, dealer or "
                 "transaction data is included.")


def build(name: str, out_root: Path, overrides: dict) -> dict:
    market = MARKETS[name]
    folder = out_root / name
    folder.mkdir(parents=True, exist_ok=True)
    kwargs = {**market["kwargs"], **overrides}
    with tempfile.TemporaryDirectory() as tmp:
        market["generator"].generate_dataset(tmp, **kwargs)
        summary = {}
        for table in LOAD_ORDER:
            raw = pd.read_csv(Path(tmp) / f"{table}.csv", low_memory=False)
            if table == "external_factors" and market["post_external"]:
                raw = market["post_external"](raw)
            clean, report = canonicalize(table, raw)
            clean.to_csv(folder / f"{table}.csv", index=False)
            summary[table] = {"rows": len(clean), "columns": len(clean.columns), **report}
    return summary


def validate(name: str, out_root: Path) -> dict:
    """Run every file through the platform's own mapping + transform, exactly as an upload would."""
    results = {}
    for table in LOAD_ORDER:
        raw = pd.read_csv(out_root / name / f"{table}.csv", dtype=str, keep_default_na=False, na_values=[""])
        proposal = propose_mapping(table, list(raw.columns))
        not_exact = {f: c.confidence for f, c in proposal.choices.items() if c.confidence != "exact"}
        _, report = transform_table(table, raw, proposal.to_mapping(), {"distance": "km"}, False, ".")
        results[table] = {"rows_in": report["rows_in"], "rows_out": report["rows_out"], "not_exact": not_exact,
                          "unmapped": proposal.unmapped, "coercion_failures": report["coercion_failures"],
                          "warnings": report["warnings"]}
    return results


def write_readme(name: str, out_root: Path, summary: dict) -> None:
    m = MARKETS[name]
    folder = out_root / name
    lines = [
        f"PredictaX sample dataset: {name}",
        "=" * 60,
        f"Built {date.today():%Y-%m-%d} by scripts/build_account_datasets.py",
        "",
        REQUIRED_NOTE,
        "",
        f"ACCOUNT TO UPLOAD TO:  {m['slug']}   (admin console -> Accounts -> {m['slug']} -> Import data)",
        "",
        "ACCOUNT SETTINGS (check under the account's Settings tab; these do not change with the upload)",
        f"  Currency ........ {m['currency']}",
        f"  Regions called .. {m['region']}",
        f"  Language ........ {m['language']}",
        "",
        "FILES (upload all six; only sales is strictly required)",
    ]
    for table in LOAD_ORDER:
        size = (folder / f"{table}.csv").stat().st_size / 1e6
        lines.append(f"  {table + '.csv':<22} {summary[table]['rows']:>9,} rows   {summary[table]['columns']:>2} columns   {size:6.1f} MB")
    lines += [
        "",
        "UPLOAD STEPS",
        "  1. Upload the six files in the Import data tab.",
        "  2. Step 2 (column matching) should show every field as 'exact match' with nothing to fix. If you see a guess, stop and tell us.",
        "  3. Set: Dates = Year-Month-Day, Decimal separator = '.', Distances = " + m["distance"] + ", Import mode = 'Replace all their data'.",
        "  4. Click 'Check the data' (should report every table as looks good), then 'Import and train'.",
        "  5. Allow a few minutes: the import loads the data, then trains the forecasting-support, segmentation and lead-close models.",
        "",
        "WHAT IS REAL",
    ] + [f"  - {t}" for t in m["real"]] + ["", "WHAT IS MODELLED (synthetic)"] + [f"  - {t}" for t in m["modelled"]] + [
        "",
        "FORMAT",
        "  Column names are the platform's own field names. Money is in whole currency units with no symbol or thousands separator,",
        "  distances are in km, energy in kWh, fuel in litres/100 km, dates are YYYY-MM-DD, booleans are True/False, gaps are empty.",
        "",
        "Do not present these files as a customer's real data.",
    ]
    (folder / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "Accounts-Datasets"))
    ap.add_argument("--only", choices=list(MARKETS))
    ap.add_argument("--sales", type=int)
    ap.add_argument("--customers", type=int)
    a = ap.parse_args()
    overrides = {k: v for k, v in (("n_sales", a.sales), ("n_customers", a.customers)) if v}
    out_root = Path(a.out)
    failed = False
    for name in ([a.only] if a.only else list(MARKETS)):
        print(f"\n=== {name} ===", flush=True)
        summary = build(name, out_root, overrides)
        checks = validate(name, out_root)
        for table in LOAD_ORDER:
            c, s = checks[table], summary[table]
            ok = not c["not_exact"] and not c["unmapped"] and not c["coercion_failures"] and c["rows_out"] == c["rows_in"] and not s["missing_required"]
            failed |= not ok
            print(f"  {table:<17} {c['rows_out']:>7,}/{c['rows_in']:<7,} rows  {'OK' if ok else 'PROBLEM'}"
                  f"{'  not-exact=' + str(c['not_exact']) if c['not_exact'] else ''}"
                  f"{'  unmapped=' + str(c['unmapped']) if c['unmapped'] else ''}"
                  f"{'  coercion=' + str(c['coercion_failures']) if c['coercion_failures'] else ''}"
                  f"{'  warn=' + str(c['warnings']) if c['warnings'] else ''}"
                  f"{'  converted=' + str(s['converted']) if s['converted'] else ''}", flush=True)
        write_readme(name, out_root, summary)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
