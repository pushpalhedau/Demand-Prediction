import streamlit as st
import os
import sys
from datetime import date
from streamlit_option_menu import option_menu

# Add current path to python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.connection import get_db_session
from database.queries import get_unique_filter_options
from utils.helpers import inject_custom_css
from dashboard.overview import render_overview
from dashboard.forecasting import render_forecasting
from dashboard.comparison import render_comparison
from dashboard.regional import render_regional
from dashboard.customers import render_customers
from dashboard.inventory import render_inventory
from dashboard.ai_insights import render_ai_insights
from dashboard.upload_data import render_upload_data
from dashboard.metrics import render_metrics

# 1. Page Configuration
st.set_page_config(
    page_title="AI Automobile Demand Intelligence Platform",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Styling Injection
inject_custom_css()

# 3. Fetch unique sidebar filter choices dynamically from DB
session = get_db_session()
try:
    options = get_unique_filter_options(session)
except Exception:
    # Fail-safe fallbacks if DB is not seeded or active
    options = {
        "regions": ["Abu Dhabi", "Ajman", "Dubai", "Fujairah", "Ras Al Khaimah", "Sharjah", "Umm Al Quwain"],
        "cities": ["Abu Dhabi City", "Al Quoz", "Business Bay", "Deira", "Downtown Dubai", "Dubai Marina", "Jumeirah", "Khalifa City", "Musaffah", "Sharjah City"],
        "categories": ["SUV", "Sedan", "Luxury", "EV", "Sports Car", "Pickup Truck", "Van/Commercial"],
        "fuel_types": ["Petrol", "Diesel", "Electric", "Hybrid"],
        "brands": ["Toyota", "Nissan", "Hyundai", "Kia", "Honda", "Mercedes-Benz", "BMW", "Audi", "Lexus", "Land Rover", "Tesla", "BYD"],
        "years": [2021, 2022, 2023, 2024, 2025]
    }
finally:
    session.close()

# 4. HEADER BRANDING
st.markdown("""
    <div style="text-align: center; margin-top: -30px; margin-bottom: 20px;">
        <h1 class="main-title"><span class="gradient-text">🚗 AI Automobile Demand Intelligence Platform</span></h1>
        <p style="color: #9ca3af; font-size: 15px; margin-top: -10px;">Enterprise Decision Support Suite — Demand Forecasting & Customer Analytics</p>
    </div>
""", unsafe_allow_html=True)

# 5. SIDEBAR NAVIGATION & GLOBAL FILTERS
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 10px 0;">
            <h3 style="color: #f3f4f6; font-size: 18px; margin-bottom: 5px;">📍 Navigation</h3>
        </div>
    """, unsafe_allow_html=True)
    
    # Sleek sidebar menu with option_menu
    selected_page = option_menu(
        menu_title=None,
        options=[
            "Executive Overview",
            "Demand Forecasting",
            "Comparative Analytics",
            "Regional Intelligence",
            "Customer Intelligence",
            "Inventory Intelligence",
            "AI Insights & Simulator",
            "Data Ingestion Engine",
            "Model Performance Metrics"
        ],
        icons=[
            "speedometer2",
            "graph-up-arrow",
            "columns-gap",
            "geo-alt",
            "people",
            "box-seam",
            "cpu",
            "cloud-arrow-up",
            "bar-chart-steps"
        ],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#06b6d4", "font-size": "15px"}, 
            "nav-link": {
                "font-size": "13px", 
                "text-align": "left", 
                "margin": "0px", 
                "color": "#9ca3af",
                "font-family": "Plus Jakarta Sans"
            },
            "nav-link-selected": {"background-color": "rgba(99, 102, 241, 0.18)", "color": "#f3f4f6", "font-weight": "600", "border-left": "4px solid #6366f1"}
        }
    )
    
    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 15px 0;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: #f3f4f6; font-size: 15px; margin-bottom: 10px;'>⚡ Global Filters</h3>", unsafe_allow_html=True)
    
    # Global Filters Inputs
    start_date = st.date_input("Start Date", value=date(2021, 1, 1))
    end_date = st.date_input("End Date", value=date(2025, 3, 31))
    
    region = st.selectbox("Emirate", options=["All"] + options["regions"])

    # Filter areas dynamically based on emirate
    if region != "All":
        # Simply load cities belonging to chosen region
        session = get_db_session()
        try:
            from database.models import Sale
            region_cities = [c[0] for c in session.query(Sale.area).filter(Sale.emirate == region).distinct().all() if c[0]]
            city_options = sorted(region_cities)
        except Exception:
            city_options = options["cities"]
        finally:
            session.close()
    else:
        city_options = options["cities"]
        
    city = st.selectbox("Area", options=["All"] + city_options)
    brand = st.selectbox("Brand", options=["All"] + options["brands"])
    category = st.selectbox("Vehicle Category", options=["All"] + options["categories"])
    fuel_type = st.selectbox("Fuel Type", options=["All"] + options["fuel_types"])
    
    # Compile global filter dictionary
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "emirate": None if region == "All" else region,
        "area": None if city == "All" else city,
        "brand": None if brand == "All" else brand,
        "vehicle_category": None if category == "All" else category,
        "fuel_type": None if fuel_type == "All" else fuel_type
    }

# 6. ROUTING MAIN VIEWS
if selected_page == "Executive Overview":
    render_overview(filters)
elif selected_page == "Demand Forecasting":
    render_forecasting(filters)
elif selected_page == "Comparative Analytics":
    render_comparison(filters)
elif selected_page == "Regional Intelligence":
    render_regional(filters)
elif selected_page == "Customer Intelligence":
    render_customers(filters)
elif selected_page == "Inventory Intelligence":
    render_inventory(filters)
elif selected_page == "AI Insights & Simulator":
    render_ai_insights(filters)
elif selected_page == "Data Ingestion Engine":
    render_upload_data()
elif selected_page == "Model Performance Metrics":
    render_metrics()
