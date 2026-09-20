"""
Backtest the platform's forecasting approach on REAL, public monthly vehicle-market data (US, from FRED).

    python scripts/backtest_public_data.py              # uses data/public/*.csv, writes docs/research/...
    python scripts/backtest_public_data.py --refresh    # re-download the series first

Rolling origin: from each origin month the models see only earlier history and forecast the next 12 months; errors are
scored against what really happened. Results are written as a markdown report with raw tables (conclusions are written
by hand in the report afterwards).
"""
from __future__ import annotations

import argparse
import time
import urllib.request
from pathlib import Path

import pandas as pd

from backend.ml import backtest as bt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "public"
REPORT = ROOT / "docs" / "research" / "forecast-backtest-public-data.md"

SERIES = {
    "TOTALNSA": "All light vehicles sold (thousand units, not seasonally adjusted)",
    "LAUTONSA": "Light-weight autos sold (thousand units, NSA)",
    "LTRUCKNSA": "Light-weight trucks sold (thousand units, NSA)",
    "MRTSSM44112USN": "Used-car dealers retail sales (million USD, NSA; includes price inflation)",
}
REGIMES = [("2008-2009 financial crisis", "2008-01-01", "2009-12-31"), ("2010-2019 steady market", "2010-01-01", "2019-12-31"),
           ("2020-2021 COVID and chip shortage", "2020-01-01", "2021-12-31"), ("2022 onward", "2022-01-01", "2030-01-01")]


def load(series_id: str, refresh: bool) -> pd.Series:
    path = DATA / f"{series_id}.csv"
    if refresh or not path.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", path)  # noqa: S310
    df = pd.read_csv(path)
    return pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(),
                     index=pd.to_datetime(df.iloc[:, 0]), name=series_id).dropna()


def pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{x * 100:.1f}%"


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def section(series_id: str, description: str, results: pd.DataFrame) -> str:
    s = bt.summarize(results)
    pick = s[s["horizon"].isin([1, 3, 6, 12])]
    wape = pick.pivot(index="horizon", columns="model", values="wape")[list(bt.MODELS)].map(pct).reset_index()
    cover = pick[pick["model"].str.startswith("prophet")].pivot(index="horizon", columns="model", values="coverage").map(pct).reset_index()
    quarter = bt.quarter_errors(results)
    quarter_tbl = pd.DataFrame({"model": quarter["model"], "quarter WAPE": quarter["wape"].map(pct), "quarter bias": quarter["bias"].map(pct),
                                "origins": quarter["n"]})
    skill = bt.skill_vs_baseline(s)
    skill_tbl = skill[skill["horizon"].isin([1, 3, 6, 12])].pivot(index="horizon", columns="model", values="skill").map(pct).reset_index()

    regime_rows = []
    for name, lo, hi in REGIMES:
        part = results[(results["origin"] >= lo) & (results["origin"] <= hi)]
        if part.empty:
            continue
        w = part.assign(e=(part["forecast"] - part["actual"]).abs()).groupby("model").apply(lambda g: g["e"].sum() / g["actual"].sum(), include_groups=False)
        regime_rows.append({"period (origin dates)": name, **{m: pct(w.get(m)) for m in bt.MODELS}, "origins": part["origin"].nunique()})
    return "\n\n".join([
        f"## {series_id}: {description}",
        f"Origins: {results['origin'].min():%b %Y} to {results['origin'].max():%b %Y}, every 3 months.",
        "**Error by forecast horizon (WAPE: total absolute error / total actual; lower is better)**", table(wape),
        "**Skill vs 'same month last year' (positive = better than that baseline, negative = worse)**", table(skill_tbl),
        "**Next-quarter total (what a dealer plans on)**", table(quarter_tbl),
        "**Error by market regime, all horizons pooled**", table(pd.DataFrame(regime_rows)),
        "**How often the actual fell inside Prophet's 95% band (should be about 95%)**", table(cover),
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--step", type=int, default=3)
    parser.add_argument("--first-origin", default="2007-12-01")
    args = parser.parse_args()

    parts, started = [], time.time()
    for series_id, description in SERIES.items():
        series = load(series_id, args.refresh)
        print(f"{series_id}: {len(series)} months to {series.index[-1]:%Y-%m}", flush=True)
        results = bt.rolling_backtest(series, horizon=12, min_train=60, step=args.step, first_origin=args.first_origin)
        results.to_csv(DATA / f"backtest_{series_id}.csv", index=False)
        parts.append(section(series_id, description, results))
        print(f"  done after {time.time() - started:.0f}s", flush=True)

    header = (f"# Forecast backtest on public market data\n\nGenerated {pd.Timestamp.now():%Y-%m-%d} by `scripts/backtest_public_data.py`. "
              "Data: US Bureau of Economic Analysis / Census series via FRED (snapshots in `data/public/`).\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(header + "\n\n" + "\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
