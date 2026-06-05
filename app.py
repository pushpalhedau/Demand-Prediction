import streamlit as st
import os
import sys
from datetime import date
from streamlit_option_menu import option_menu

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.connection import get_db_session
from database.queries import get_unique_filter_options
from utils.helpers import inject_custom_css

from dashboard.overview import render_overview
from dashboard.forecasting import render_forecasting
from dashboard.price_intelligence import render_price_intelligence
from dashboard.comparison import render_comparison
from dashboard.regional import render_regional
from dashboard.customers import render_customers
from dashboard.inventory import render_inventory
from dashboard.ai_insights import render_ai_insights
from dashboard.sentiment_analysis import render_sentiment_analysis

# ── Page Config ──────────────────────────────────────────
st.set_page_config(
    page_title="RE Demand Intelligence",
    page_icon="RE",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_css()

# ── Load filter options ───────────────────────────────────
session = get_db_session()
try:
    options = get_unique_filter_options(session)
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
    session.close()

# ── Header ────────────────────────────────────────────────
st.markdown("""
    <div style="text-align:center; margin-top:-28px; margin-bottom:18px;">
        <h1 class="main-title" style="font-size:32px; margin-bottom:4px;">
            <span class="gradient-text">Real Estate Demand Intelligence Platform</span>
        </h1>
        <p class="subtitle-text">
            Enterprise AI Suite — Demand Forecasting · Price Intelligence · Buyer Analytics · Market Simulation
        </p>
    </div>
""", unsafe_allow_html=True)

# ── Sidebar Navigation ────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <div style="text-align:center; padding:8px 0 12px 0;">
            <div style="color:#10b981; font-weight:700; font-size:13px; letter-spacing:0.05em;">
                RE INTELLIGENCE
            </div>
            <div style="color:#4b5563; font-size:10px; letter-spacing:0.08em; margin-top:2px;">
                POWERED BY AI & PROPHET
            </div>
        </div>
    """, unsafe_allow_html=True)

    selected_page = option_menu(
        menu_title=None,
        options=[
            "Executive Overview",
            "Demand Forecasting",
            "Price Intelligence",
            "Regional Intelligence",
            "Inventory Intelligence",
            "Customer Intelligence",
            "Comparative Analytics",
            "Market Insights",
            "Sentiment Analysis",
        ],
        icons=[
            "speedometer2",
            "graph-up-arrow",
            "bar-chart-line",
            "geo-alt",
            "building",
            "people",
            "columns-gap",
            "cpu",
            "chat-left-quote",
        ],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {
                "padding": "0!important",
                "background-color": "transparent",
                "font-family": "'Plus Jakarta Sans', sans-serif",
            },
            "icon": {"color": "#10b981", "font-size": "14px"},
            "nav-link": {
                "font-size": "13px",
                "text-align": "left",
                "margin": "0px",
                "color": "#6b7280",
                "padding": "8px 12px",
                "border-radius": "8px",
                "font-family": "'Plus Jakarta Sans', sans-serif",
            },
            "nav-link-selected": {
                "background": "rgba(16, 185, 129, 0.12)",
                "color": "#f0f4f8",
                "font-weight": "600",
                "border-left": "3px solid #10b981",
                "font-family": "'Plus Jakarta Sans', sans-serif",
            },
        },
    )

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.06);margin:14px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:11px;color:#374151;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.10em;margin-bottom:10px;'>Global Filters</p>",
        unsafe_allow_html=True,
    )

    start_date = st.date_input("Start Date", value=date(2021, 1, 1))
    end_date = st.date_input("End Date", value=date(2025, 3, 31))

    city = st.selectbox("City", ["All"] + options["cities"])
    region = st.selectbox("Region", ["All"] + options["regions"])
    prop_type = st.selectbox("Property Type", ["All"] + options["property_types"])
    prop_cat = st.selectbox("Category", ["All"] + options["property_categories"])
    bedrooms = st.selectbox("Bedrooms", ["All"] + options["bedrooms"])

    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "city": None if city == "All" else city,
        "region": None if region == "All" else region,
        "property_type": None if prop_type == "All" else prop_type,
        "property_category": None if prop_cat == "All" else prop_cat,
        "bedrooms": None if bedrooms == "All" else bedrooms,
    }

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.06);margin:14px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown("""
        <div style="font-size:10px;color:#374151;text-align:center;line-height:1.6">
            UAE Real Estate · 7 Emirates<br>
            Jan 2021 – 2026 · 100K+ Transactions
        </div>
    """, unsafe_allow_html=True)

# ── Page Routing ──────────────────────────────────────────
if selected_page == "Executive Overview":
    render_overview(filters)
elif selected_page == "Demand Forecasting":
    render_forecasting(filters)
elif selected_page == "Price Intelligence":
    render_price_intelligence(filters)
elif selected_page == "Regional Intelligence":
    render_regional(filters)
elif selected_page == "Inventory Intelligence":
    render_inventory(filters)
elif selected_page == "Customer Intelligence":
    render_customers(filters)
elif selected_page == "Comparative Analytics":
    render_comparison(filters)
elif selected_page == "Market Insights":
    render_ai_insights(filters)
elif selected_page == "Sentiment Analysis":
    render_sentiment_analysis(filters)
