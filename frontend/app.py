"""
UAE Real Estate Decision Intelligence Platform
Streamlit Frontend — main entry point
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root (Demand-Prediction/) is in sys.path so that
# 'frontend' and 'backend' are importable as top-level packages.
# Streamlit adds frontend/ to sys.path by default; we need one level up.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

# Page config MUST be first Streamlit call
st.set_page_config(
    page_title="UAE Real Estate Intelligence Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)

import frontend.api_client as api
from frontend.components.theme import THEME_CSS, LOADER_SCRIPT
from frontend.components.kpi_cards import KPI_CSS
from frontend.pages import p1_executive, p2_forecast, p3_market, p4_customer, p5_inventory, p6_ai_studio


def main():
    # Inject global CSS + instant loader script
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    st.markdown(LOADER_SCRIPT, unsafe_allow_html=True)

    # ── Platform Header ──────────────────────────────────────────
    st.markdown(
        """
        <div style="padding:20px 0 4px;border-bottom:1px solid #1e1e3f;margin-bottom:20px">
          <div style="display:flex;align-items:center;gap:14px">
            <div>
              <div style="font-size:22px;font-weight:800;color:#f1f5f9;letter-spacing:-0.03em">
                UAE Real Estate Intelligence Platform
              </div>
              <div style="font-size:12px;color:#64748b;margin-top:2px">
                AI-Powered Decision Intelligence • Powered by DLD Data Lake • GROQ AI
              </div>
            </div>
            <div style="margin-left:auto">
              <span style="background:#1e1e3f;color:#6366f1;font-size:10px;font-weight:700;
                           text-transform:uppercase;letter-spacing:.1em;padding:4px 12px;
                           border-radius:100px;border:1px solid #3730a3">
                v2.0 ENTERPRISE
              </span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Backend Health Check ─────────────────────────────────────
    health = api.health_check()
    if health.get("status") != "healthy":
        st.error(
            "Backend is not running. Please start FastAPI first:\n\n"
            "`uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`\n\n"
            "Or run `start.bat` to launch both services."
        )
        st.stop()

    datasets_loaded = health.get("datasets_loaded", 0)
    if datasets_loaded > 0:
        st.sidebar.markdown(
            f'<div style="font-size:11px;color:#10b981;padding:6px 0">✓ {datasets_loaded} datasets loaded</div>',
            unsafe_allow_html=True,
        )

    # ── Sidebar Filters ──────────────────────────────────────────
    st.sidebar.markdown(
        '<div style="font-size:13px;font-weight:700;color:#f1f5f9;padding:8px 0 4px">Filters</div>',
        unsafe_allow_html=True,
    )

    _raw_year = st.sidebar.selectbox(
        "Year", [2024, 2023, 2022, 2021, 2020, 2019], index=0
    )
    _raw_area = st.sidebar.selectbox(
        "Area Focus",
        ["All UAE", "Business Bay", "Downtown Dubai", "Dubai Marina",
         "Dubai South", "JVC", "JLT", "Al Barsha", "Jumeirah Village",
         "Palm Jumeirah", "Dubai Creek Harbour"],
        index=0,
    )
    _raw_ptype = st.sidebar.selectbox(
        "Property Type",
        ["All", "Apartment", "Villa", "Townhouse", "Penthouse", "Studio", "Commercial"],
        index=0,
    )

    # Normalise to None so API calls treat "All" selections as unfiltered
    filters = {
        "year":          _raw_year,
        "area":          None if _raw_area  == "All UAE" else _raw_area,
        "property_type": None if _raw_ptype == "All"     else _raw_ptype,
    }

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<div style="font-size:11px;color:#64748b">Platform Status</div>',
        unsafe_allow_html=True,
    )
    record_counts = health.get("dataset_record_counts", {})
    tx_count = record_counts.get("transactions", 0)
    if tx_count:
        st.sidebar.markdown(
            f'<div style="font-size:11px;color:#94a3b8">{tx_count:,} transactions</div>',
            unsafe_allow_html=True,
        )

    # ── Main Navigation Tabs ────────────────────────────────────
    tab_labels = [
        "Executive Command Center",
        "Forecast & Demand",
        "Market & Opportunity",
        "Customer & Pricing",
        "Project & Inventory",
        "AI Strategy Studio",
    ]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        p1_executive.render(filters)

    with tabs[1]:
        p2_forecast.render(filters)

    with tabs[2]:
        p3_market.render(filters)

    with tabs[3]:
        p4_customer.render(filters)

    with tabs[4]:
        p5_inventory.render(filters)

    with tabs[5]:
        p6_ai_studio.render(filters)


if __name__ == "__main__":
    main()
