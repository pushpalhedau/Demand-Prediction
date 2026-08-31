import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from database.connection import get_db_session
from database.queries import get_dealer_performance_leaderboard
from utils.helpers import (
    _section, _base_layout, _fmt_money, _compact, _pct_label,
    _INK,
)

# ─────────────────────────────────────────────────────────────────────────────
# Estimated gross per new unit (front-end + F&I), 2024 industry benchmarks.
#   Front-end new-vehicle gross ≈ $2,250 average — $1,950 domestic / $1,700
#   import / $5,679 luxury (NADA 2024; Presidio-NCM FY2024). F&I per new retail
#   unit ≈ $2,000–2,400 (NADA 2024 ≈ $1,581 blended new+used; Haig public
#   dealers ≈ $2,400/vehicle retailed). Applied to each store's franchise so
#   "Est. gross" scales with the store's own volume and brand mix. This is a
#   benchmark estimate, not booked gross — the Sale table carries no cost basis.
_GROSS_PER_UNIT = {"luxury": 8_100, "import": 3_750, "domestic": 4_050}
_LUXURY_BRANDS = {"BMW", "Mercedes-Benz", "Lexus"}
_MASS_IMPORT_BRANDS = {"Toyota", "Honda", "Nissan", "Subaru", "Hyundai", "Kia", "Volkswagen"}

# "Pace vs the store's own annual target", coloured the same way on the map and
# the ranking bar so the hue means one thing everywhere. Targets carry a +5%
# stretch, so ~95% of target ≈ holding last year's volume: that's the neutral
# (yellow) midpoint; below ~90% goes red, at/above target goes green.
_ATTAINMENT_SCALE = "RdYlGn"
_ATTAINMENT_MID = 95
_ATTAINMENT_RANGE = (84, 104)   # clamps the colour, not the underlying number
_BEHIND_PLAN_PCT = 90   # materially short of target — worth a GM's attention


def _origin_bucket(brand: str) -> str:
    if brand in _LUXURY_BRANDS:
        return "luxury"
    if brand in _MASS_IMPORT_BRANDS:
        return "import"
    return "domestic"


def render_regional(filters: dict):
    """
    Store Performance — how each of the dealer group's rooftops is tracking:
    units and revenue for the selected window, pace against the store's own
    annual target, year-over-year growth, and showroom conversion. One regional
    group's own stores, not a market or a territory map.
    """
    session = get_db_session()
    try:
        st.markdown(
            "<h2 class='gradient-text' style='margin-bottom:18px;'>Store Performance</h2>",
            unsafe_allow_html=True,
        )

        df = get_dealer_performance_leaderboard(session, filters)
        if df.empty:
            st.warning("No store sales for the active filters.")
            return

        df = df.copy()
        df["units_sold"] = df["units_sold"].fillna(0).astype(int)
        df["revenue"] = df["revenue"].fillna(0)
        df["est_gross"] = df.apply(
            lambda r: r["units_sold"] * _GROSS_PER_UNIT[_origin_bucket(r["brand"])], axis=1
        )
        df["label"] = df["dealer_name"] + " · " + df["city"]
        has_target = df["attainment_pct"].notna()

        # ── Headline row ────────────────────────────────────────────────────
        behind = int((df.loc[has_target, "attainment_pct"] < _BEHIND_PLAN_PCT).sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Rooftops reporting", f"{len(df)}")
        c2.metric("Units this period", f"{df['units_sold'].sum():,}")
        c3.metric(
            "Stores behind plan", f"{behind} of {int(has_target.sum())}",
            help=f"Trailing-12-month units below {_BEHIND_PLAN_PCT}% of the store's "
                 "own annual target.",
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 1. Footprint map ───────────────────────────────────────────────
        _section("Where the rooftops are")
        gps = df[df["latitude"].notna() & df["longitude"].notna() & (df["units_sold"] > 0)]
        if gps.empty:
            st.info("No store coordinates available for the active filters.")
        else:
            lat0, lat1 = gps["latitude"].min(), gps["latitude"].max()
            lon0, lon1 = gps["longitude"].min(), gps["longitude"].max()
            span = max(lat1 - lat0, (lon1 - lon0) * 0.62, 1.0)
            zoom = float(np.clip(8.7 - np.log2(span), 3.2, 6.5))

            gps = gps.assign(
                _attain=gps["attainment_pct"].fillna(100).clip(*_ATTAINMENT_RANGE),
                _yoy=gps["yoy_units_pct"].map(lambda v: _pct_label(v, 1)),
                _att_txt=gps["attainment_pct"].map(
                    lambda v: f"{v:.0f}% of target" if pd.notna(v) else "no target set"
                ),
                _rev=gps["revenue"].map(_fmt_money),
            )
            fig_map = px.scatter_map(
                gps, lat="latitude", lon="longitude",
                size="units_sold", size_max=24,
                color="_attain", color_continuous_scale=_ATTAINMENT_SCALE,
                range_color=_ATTAINMENT_RANGE, color_continuous_midpoint=_ATTAINMENT_MID,
                hover_name="dealer_name",
                custom_data=["brand", "city", "state", "units_sold", "_rev", "_att_txt", "_yoy"],
                map_style="carto-darkmatter",
                zoom=zoom, center={"lat": (lat0 + lat1) / 2, "lon": (lon0 + lon1) / 2},
            )
            fig_map.update_traces(marker=dict(opacity=0.85))
            fig_map.update_traces(hovertemplate=(
                "<b>%{hovertext}</b><br>"
                "%{customdata[0]} · %{customdata[1]}, %{customdata[2]}<br>"
                "%{customdata[3]:,} units · %{customdata[4]}<br>"
                "%{customdata[5]} · %{customdata[6]} YoY<extra></extra>"
            ))
            fig_map.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color=_INK, family="Plus Jakarta Sans"),
                margin=dict(l=0, r=0, t=0, b=0), height=440,
                coloraxis_colorbar=dict(
                    title="Pace vs<br>target", ticksuffix="%", thickness=12, len=0.7,
                ),
            )
            st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 2. Store ranking ──────────────────────────────────────────────
        _section("Rooftops by units sold")
        rank = df.sort_values("units_sold")
        fig_bar = px.bar(
            rank, x="units_sold", y="label", orientation="h",
            color=rank["attainment_pct"].fillna(100).clip(*_ATTAINMENT_RANGE),
            color_continuous_scale=_ATTAINMENT_SCALE, range_color=_ATTAINMENT_RANGE,
            color_continuous_midpoint=_ATTAINMENT_MID,
        )
        fig_bar.update_traces(
            text=rank["units_sold"].map(_compact), textposition="outside",
            cliponaxis=False, hoverinfo="skip",
        )
        fig_bar.update_layout(**_base_layout(
            height=max(360, 24 * len(rank)),
            margin=dict(l=0, r=60, t=6, b=0),
        ))
        fig_bar.update_xaxes(title="Units sold", showgrid=True, gridcolor="rgba(255,255,255,0.06)")
        fig_bar.update_yaxes(title="")
        fig_bar.update_layout(coloraxis_colorbar=dict(
            title="Pace vs<br>target", ticksuffix="%", thickness=12, len=0.7,
        ))
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 3. Store scorecard ────────────────────────────────────────────
        _section("Store scorecard")
        board = pd.DataFrame({
            "Store": df["dealer_name"],
            "Franchise": df["brand"],
            "State": df["state"],
            "Units": df["units_sold"],
            "Revenue ($M)": (df["revenue"] / 1e6).round(1),
            "YoY units %": df["yoy_units_pct"].round(1),
            "Pace vs target %": df["attainment_pct"].round(0),
            "Est. gross ($M)": (df["est_gross"] / 1e6).round(2),
            "Close rate %": (df["close_rate"] * 100).round(0),
            "Avg days to close": df["avg_days_to_close"].round(0),
            "Top segment": df["top_category"].fillna("–"),
        }).sort_values("Units", ascending=False)
        st.dataframe(
            board, use_container_width=True, hide_index=True, height=460,
            column_config={
                "Units": st.column_config.NumberColumn(format="%d"),
                "Revenue ($M)": st.column_config.NumberColumn(format="%.1f"),
                "YoY units %": st.column_config.NumberColumn(format="%.1f%%"),
                "Pace vs target %": st.column_config.NumberColumn(format="%.0f%%"),
                "Est. gross ($M)": st.column_config.NumberColumn(format="%.2f"),
                "Close rate %": st.column_config.NumberColumn(format="%.0f%%"),
                "Avg days to close": st.column_config.NumberColumn(format="%.0f"),
            },
        )

        # ── 4. Both ends of the network ───────────────────────────────────
        ranked = df[has_target].sort_values("attainment_pct")
        if not ranked.empty:
            weak = ranked.iloc[0]
            strong = ranked.iloc[-1]
            lcol, rcol = st.columns(2)
            with lcol:
                st.success(
                    f"**Carrying the group — {strong['dealer_name']}**  \n"
                    f"{strong['units_sold']:,} units this period · "
                    f"{strong['attainment_pct']:.0f}% of target · "
                    f"{_pct_label(strong['yoy_units_pct'], 1)} YoY."
                )
            with rcol:
                extra = ""
                also_down = ranked[
                    (ranked["yoy_units_pct"] < 0)
                    & (ranked["dealer_name"] != weak["dealer_name"])
                ]
                if not also_down.empty:
                    others = ", ".join(also_down["dealer_name"].head(3))
                    extra = f"  \nAlso down year-over-year: {others}."
                st.warning(
                    f"**Needs attention — {weak['dealer_name']}**  \n"
                    f"{weak['units_sold']:,} units this period · "
                    f"{weak['attainment_pct']:.0f}% of target · "
                    f"{_pct_label(weak['yoy_units_pct'], 1)} YoY.{extra}"
                )

    except Exception as e:  # pragma: no cover - surfaced in the UI
        st.error(f"Error rendering Store Performance: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
