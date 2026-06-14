import streamlit as st
import os
import sys
from datetime import date
from streamlit_option_menu import option_menu

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.connection import get_db_session
from database.queries import get_unique_filter_options
from utils.helpers import inject_custom_css

# Existing page renderers
from dashboard.overview import render_overview
from dashboard.forecasting import render_forecasting
from dashboard.price_intelligence import render_price_intelligence
from dashboard.comparison import render_comparison
from dashboard.regional import render_regional
from dashboard.customers import render_customers
from dashboard.inventory import render_inventory
from dashboard.ai_insights import render_ai_insights
from dashboard.sentiment_analysis import render_sentiment_analysis

# New dedicated screens
from dashboard.lead_intelligence import render_lead_intelligence
from dashboard.project_performance import render_project_performance
from dashboard.construction_intelligence import render_construction_intelligence
from dashboard.rental_trends import render_rental_trends
from dashboard.financial_intelligence import render_financial_intelligence
from dashboard.investor_intelligence import render_investor_intelligence
from dashboard.document_intelligence import render_document_intelligence
from dashboard.strategic_planning import render_strategic_planning

# ── Page Config ──────────────────────────────────────────
st.set_page_config(
    page_title="CEO Real Estate Intelligence",
    page_icon="RE",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_css()

# ── Load filter options ───────────────────────────────────
_init_session = get_db_session()
try:
    options = get_unique_filter_options(_init_session)
except Exception:
    options = {
        "cities": ["Dubai", "Abu Dhabi", "Sharjah", "Ras Al Khaimah", "Ajman", "Fujairah", "Umm Al Quwain"],
        "regions": ["South UAE", "North UAE", "Central UAE"],
        "emirates": ["Dubai", "Abu Dhabi", "Sharjah", "Ras Al Khaimah", "Ajman", "Fujairah", "Umm Al Quwain"],
        "property_types": ["Apartment", "Villa", "Townhouse", "Penthouse", "Plot", "Commercial", "Studio"],
        "property_categories": ["Affordable", "Mid-Market", "Premium", "Luxury", "Ultra-Luxury"],
        "bedrooms": ["Studio", "1BR", "2BR", "3BR", "4BR", "5BR+"],
        "years": [2021, 2022, 2023, 2024, 2025, 2026],
    }
finally:
    _init_session.close()

# ── Sub-page map ──────────────────────────────────────────
SUB_PAGES = {
    "Home":       ["CEO Dashboard", "AI Copilot"],
    "Sales":      ["Sales Performance", "Lead Intelligence", "Customer 360"],
    "Projects":   ["Project Performance", "Construction Intelligence"],
    "Market":     ["Demand Forecast", "Market Intelligence", "Rental Trends"],
    "Finance":    ["Financial Intelligence", "Risk Management"],
    "Investors":  ["Investor Intelligence"],
    "Operations": ["Inventory Intelligence", "Pricing Intelligence", "Document Intelligence", "Strategic Planning"],
}

TAB_ICONS = ["house-fill", "graph-up-arrow", "buildings", "globe-americas", "cash-stack", "bar-chart-line-fill", "gear-fill"]

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <div style="text-align:center; padding:8px 0 14px 0;">
            <div style="color:#10b981; font-weight:700; font-size:15px; letter-spacing:0.05em;">
                CEO INTELLIGENCE
            </div>
            <div style="color:#4b5563; font-size:10px; letter-spacing:0.08em; margin-top:2px;">
                UAE REAL ESTATE PLATFORM
            </div>
        </div>
    """, unsafe_allow_html=True)

    _nav_style = {
        "container": {"padding": "0!important", "background-color": "transparent"},
        "icon": {"color": "#10b981", "font-size": "13px"},
        "nav-link": {
            "font-size": "12px",
            "text-align": "left",
            "margin": "1px 0",
            "color": "#6b7280",
            "padding": "7px 10px",
            "border-radius": "6px",
            "font-family": "'Plus Jakarta Sans', sans-serif",
        },
        "nav-link-selected": {
            "background": "rgba(16, 185, 129, 0.15)",
            "color": "#f0f4f8",
            "font-weight": "700",
            "border-left": "3px solid #10b981",
        },
    }

    # Level 1 — Tab selector
    active_tab = option_menu(
        menu_title=None,
        options=list(SUB_PAGES.keys()),
        icons=TAB_ICONS,
        default_index=0,
        key="main_tab",
        styles=_nav_style,
    )

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.06);margin:8px 0;'>",
        unsafe_allow_html=True,
    )

    # Level 2 — Sub-page selector
    sub_options = SUB_PAGES[active_tab]
    _sub_style = {
        "container": {"padding": "0!important", "background-color": "transparent"},
        "icon": {"color": "#4b5563", "font-size": "10px"},
        "nav-link": {
            "font-size": "12px",
            "text-align": "left",
            "margin": "1px 0",
            "color": "#6b7280",
            "padding": "6px 10px",
            "border-radius": "6px",
            "font-family": "'Plus Jakarta Sans', sans-serif",
        },
        "nav-link-selected": {
            "background": "rgba(99, 102, 241, 0.12)",
            "color": "#c7d2fe",
            "font-weight": "600",
            "border-left": "2px solid #6366f1",
        },
    }

    if len(sub_options) > 1:
        active_sub = option_menu(
            menu_title=None,
            options=sub_options,
            icons=["chevron-right"] * len(sub_options),
            default_index=0,
            key=f"sub_{active_tab}",
            styles=_sub_style,
        )
    else:
        active_sub = sub_options[0]

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.06);margin:10px 0;'>",
        unsafe_allow_html=True,
    )

    # Global Filters
    st.markdown(
        "<p style='font-size:11px;color:#374151;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.10em;margin-bottom:8px;'>Global Filters</p>",
        unsafe_allow_html=True,
    )

    start_date = st.date_input("Start Date", value=date(2021, 1, 1))
    end_date = st.date_input("End Date", value=date(2025, 3, 31))
    city = st.selectbox("City", ["All"] + options["cities"])
    prop_type = st.selectbox("Property Type", ["All"] + options["property_types"])
    prop_cat = st.selectbox("Category", ["All"] + options["property_categories"])

    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "city": None if city == "All" else city,
        "property_type": None if prop_type == "All" else prop_type,
        "property_category": None if prop_cat == "All" else prop_cat,
    }

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.06);margin:10px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown("""
        <div style="font-size:10px;color:#374151;text-align:center;line-height:1.6">
            UAE Real Estate · 7 Emirates<br>
            Jan 2019 – 2026 · 13 Datasets
        </div>
    """, unsafe_allow_html=True)

# ── Page Routing ──────────────────────────────────────────
db_session = get_db_session()
try:
    if active_tab == "Home":
        if active_sub == "CEO Dashboard":
            from dashboard.home_ceo import render_ceo_dashboard
            render_ceo_dashboard(filters, db_session)
        elif active_sub == "AI Copilot":
            from dashboard.home_copilot import render_ai_copilot
            render_ai_copilot(db_session)

    elif active_tab == "Sales":
        if active_sub == "Sales Performance":
            render_comparison(filters)
        elif active_sub == "Lead Intelligence":
            render_lead_intelligence(filters)
        elif active_sub == "Customer 360":
            render_customers(filters)

    elif active_tab == "Projects":
        if active_sub == "Project Performance":
            render_project_performance(filters)
        elif active_sub == "Construction Intelligence":
            render_construction_intelligence(filters)

    elif active_tab == "Market":
        if active_sub == "Demand Forecast":
            render_forecasting(filters)
        elif active_sub == "Market Intelligence":
            render_ai_insights(filters)
        elif active_sub == "Rental Trends":
            render_rental_trends(filters)

    elif active_tab == "Finance":
        if active_sub == "Financial Intelligence":
            render_financial_intelligence(filters)
        elif active_sub == "Risk Management":
            render_sentiment_analysis(filters)

    elif active_tab == "Investors":
        render_investor_intelligence(filters)

    elif active_tab == "Operations":
        if active_sub == "Inventory Intelligence":
            render_inventory(filters)
        elif active_sub == "Pricing Intelligence":
            render_price_intelligence(filters)
        elif active_sub == "Document Intelligence":
            render_document_intelligence(filters)
        elif active_sub == "Strategic Planning":
            render_strategic_planning(filters)
finally:
    db_session.close()
