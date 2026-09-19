"""Comparative Analytics: year-over-year tracking and what is driving the movement."""
import pandas as pd

from backend.analytics import yoy_attribution as ya
from backend.core.formatting import compact_num, fmt_money
from backend.db.session import with_session
from backend.repositories import sales as sales_repo
from backend.services.overview import project_series

SPECIFIC_LABEL = ya.SPECIFIC_LABEL
movement_sentences = ya.movement_sentences
__all__ = ["SPECIFIC_LABEL", "driver_split", "drivers", "movement_sentences", "project_series", "scope_monthly_trend",
           "tracking", "yoy_summary"]

DIMENSIONS = ("store", "brand", "category")


@with_session
def yoy_summary(session, filters: dict, measure: str) -> dict | None:
    return ya.summary(session, filters, measure)


@with_session
def driver_split(session, filters: dict, dimension: str, measure: str) -> pd.DataFrame | None:
    return ya.driver_split(session, filters, dimension, measure)


@with_session
def scope_monthly_trend(session, filters: dict) -> pd.DataFrame:
    return sales_repo.get_scope_monthly_trend(session, filters)


def tracking(filters: dict, measure: str) -> dict:
    """
    This calendar year against last on a Jan–Dec axis, with the rest of the current year filled in as a seasonal
    forecast. `measure` is "units" or "revenue".
    """
    summary = yoy_summary(filters, measure)
    if summary is None:
        return {"status": "no_sales"}
    trend = scope_monthly_trend(filters)
    if trend.empty:
        return {"status": "no_history"}

    series = trend.set_index("date")["units" if measure == "units" else "revenue"].astype(float).sort_index()
    # A half-booked trailing month would anchor both the booked line and the forecast too low.
    if len(series) >= 14 and series.iloc[-1] < 0.55 * series.iloc[-13:-1].mean():
        series = series.iloc[:-1]

    year = int(series.index[-1].year)
    last_year = series[series.index.year == year - 1]
    this_year = series[series.index.year == year]
    months_ahead = 12 - len(this_year)
    forecast = project_series(series, months_ahead) if months_ahead > 0 else pd.Series(dtype=float)
    forecast = forecast[forecast.index.year == year]

    def by_month(s: pd.Series) -> dict[int, float]:
        return {int(d.month): float(v) for d, v in s.items()}

    ly, cy, fc = by_month(last_year), by_month(this_year), by_month(forecast)
    booked_months = sorted(cy)
    bridge_at = booked_months[-1] if booked_months else None
    rows = []
    for m in range(1, 13):
        rows.append({
            "month": m,
            "last_year": ly.get(m),
            "booked": cy.get(m),
            # The forecast line starts at the last booked month so the two segments join.
            "forecast": cy[m] if (fc and m == bridge_at) else fc.get(m),
        })

    ly_total = float(last_year.sum())
    projected_total = float(this_year.sum() + forecast.sum())
    return {
        "status": "ok",
        "windows": summary["windows"],
        "comparable": summary["comparable"],
        "year": year,
        "rows": rows,
        "has_forecast": bool(fc),
        "complete_year": len(this_year) >= 12,
        "projected_total": projected_total,
        "last_year_total": ly_total,
        "projected_yoy_pct": (projected_total / ly_total - 1) * 100 if ly_total else None,
    }


def drivers(filters: dict, dimension: str, measure: str, only_significant: bool = False) -> dict:
    """What moved the year-over-year change: each entity's move split into the group-wide part and its own part."""
    split = driver_split(filters, dimension, measure)
    if split is None or split.empty:
        return {"status": "no_prior_year"}
    n_significant = int(split["significant"].sum())
    shown = split[split["significant"]] if (only_significant and n_significant >= 3) else split
    shown = shown.reindex(shown["specific"].abs().sort_values(ascending=False).index)
    cap = 16 if dimension == "store" else 12
    shown = shown.head(cap).sort_values("specific")
    formatter = compact_num if measure == "units" else fmt_money
    return {
        "status": "ok",
        "dimension": dimension,
        "specific_label": SPECIFIC_LABEL.get(dimension, "Specific"),
        "n_significant": n_significant,
        "rows": shown[["name", "total", "structural", "specific", "significant"]],
        "sentences": movement_sentences(split, dimension, measure, formatter, limit=3),
    }
