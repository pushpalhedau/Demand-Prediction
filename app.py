import streamlit as st
import os
import sys
from datetime import date
from streamlit_option_menu import option_menu

# Add current path to python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.connection import get_db_session
from database.queries import get_unique_filter_options, get_india_filter_options
from utils.helpers import inject_custom_css
from dashboard.overview import render_overview
from dashboard.forecasting import render_forecasting
from dashboard.comparison import render_comparison
from dashboard.regional import render_regional
from dashboard.customers import render_customers
from dashboard.inventory import render_inventory
from dashboard.ai_insights import render_ai_insights
from dashboard.sentiment_analysis import render_sentiment_analysis
# from dashboard.upload_data import render_upload_data
# from dashboard.metrics import render_metrics

# 1. Page Configuration
st.set_page_config(
    page_title="Automobile Demand Intelligence Platform",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Styling Injection
inject_custom_css()

# 3. Fetch unique sidebar filter choices dynamically from DB
session = get_db_session()
try:
    # Try India filter options first (VAHAN data); fall back to UAE options
    india_options = get_india_filter_options(session)
    if india_options.get("regions"):
        options = india_options
    else:
        options = get_unique_filter_options(session)
except Exception:
    options = {}
finally:
    session.close()

# Fallback defaults (India-centric)
if not options.get("regions"):
    options = {
        "regions": [
            "Andhra Pradesh", "Assam", "Bihar", "Chandigarh", "Delhi",
            "Gujarat", "Haryana", "Karnataka", "Kerala", "Madhya Pradesh",
            "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu",
            "Telangana", "Uttar Pradesh", "Uttarakhand", "West Bengal", "All India",
        ],
        "cities": [],
        "categories": ["Motor Car", "Motor Cycle", "Three Wheeler", "Goods Vehicle", "Bus/Minibus"],
        "fuel_types": ["Petrol", "Diesel", "Electric", "CNG", "Hybrid"],
        "brands": [
            "Maruti Suzuki", "Hyundai", "Tata Motors", "Mahindra", "Kia",
            "Honda", "Toyota", "MG Motor", "Renault", "Nissan",
            "Bajaj", "Hero MotoCorp", "TVS", "Ola Electric",
        ],
        "years": list(range(2019, 2027)),
    }

# 4. HEADER BRANDING
st.markdown("""
    <div style="text-align: center; margin-top: -30px; margin-bottom: 20px;">
        <h1 class="main-title"><span class="gradient-text">🚗 Automobile Demand Intelligence Platform</span></h1>
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
            "Insights & Simulator",
            "Sentimental  analysis",
            # "Data Ingestion Engine",
            # "Model Performance Metrics"
        ],
        icons=[
            "speedometer2",
            "graph-up-arrow",
            "columns-gap",
            "geo-alt",
            "people",
            "box-seam",
            "cpu",
            "chat-left-quote",
            # "cloud-arrow-up",
            # "bar-chart-steps"
        ],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent", "font-family": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"},
            "icon": {"color": "#06b6d4", "font-size": "15px"}, 
            "nav-link": {
                "font-size": "13px", 
                "text-align": "left", 
                "margin": "0px", 
                "color": "#9ca3af",
                "font-family": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
            },
            "nav-link-selected": {
                "background-color": "rgba(99, 102, 241, 0.18)", 
                "color": "#f3f4f6", 
                "font-weight": "600", 
                "border-left": "4px solid #6366f1",
                "font-family": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
            }
        }
    )
    
    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 15px 0;'>", unsafe_allow_html=True)
    
    # Inject custom CSS for global filter fonts
    st.markdown("""
        <style>
            /* Apply Plus Jakarta Sans to all Streamlit widget labels */
            div[data-testid="stWidgetLabel"] p,
            .stDateInput label,
            .stSelectbox label,
            .stDateInput input,
            .stSelectbox div[data-baseweb="select"] div[role="button"]
            {
                font-family: "Plus Jakarta Sans", sans-serif !important;
            }
        </style>
    """, unsafe_allow_html=True)
    st.markdown("<h3 style='color: #f3f4f6; font-size: 15px; margin-bottom: 10px;'>⚡ Global Filters</h3>", unsafe_allow_html=True)
    
    # Global Filters Inputs
    start_date = st.date_input("Start Date", value=date(2019, 1, 1))
    end_date = st.date_input("End Date", value=date(2026, 6, 30))

    region = st.selectbox("State", options=["All"] + options["regions"])

    # Filter RTOs dynamically based on selected state
    if region != "All":
        session = get_db_session()
        try:
            from database.models import Registration
            rto_list = [c[0] for c in session.query(Registration.rto_code).filter(
                Registration.state == region, Registration.rto_code != None, Registration.rto_code != ""
            ).distinct().all() if c[0]]
            city_options = sorted(rto_list)
        except Exception:
            city_options = options.get("cities", [])
        finally:
            session.close()
    else:
        city_options = options.get("cities", [])

    city = st.selectbox("RTO / Area", options=["All"] + city_options)
    brand = st.selectbox("Brand", options=["All"] + options["brands"])
    category = st.selectbox("Vehicle Category", options=["All"] + options["categories"])
    fuel_type = st.selectbox("Fuel Type", options=["All"] + options["fuel_types"])

    # Compile global filter dictionary (state/rto keys for India; emirate/area as aliases for UAE legacy)
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "state": None if region == "All" else region,
        "emirate": None if region == "All" else region,   # alias for UAE legacy queries
        "rto": None if city == "All" else city,
        "area": None if city == "All" else city,           # alias for UAE legacy queries
        "brand": None if brand == "All" else brand,
        "vehicle_category": None if category == "All" else category,
        "fuel_type": None if fuel_type == "All" else fuel_type,
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
elif selected_page == "Insights & Simulator":
    render_ai_insights(filters)
elif selected_page == "Sentimental  analysis":
    render_sentiment_analysis(filters)
# elif selected_page == "Data Ingestion Engine":
#     render_upload_data()
# elif selected_page == "Model Performance Metrics":
#     render_metrics()
