import streamlit as st
import os
import sys
from datetime import date
from streamlit_option_menu import option_menu

# Add current path to python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.connection import get_db_session, set_data_mode, get_data_mode
from database.queries import get_unique_filter_options
from utils.helpers import inject_custom_css
from dashboard.overview import render_overview
from dashboard.forecasting import render_forecasting
from dashboard.comparison import render_comparison
from dashboard.regional import render_regional
from dashboard.customers import render_customers
from dashboard.inventory import render_inventory
# from dashboard.ai_insights import render_ai_insights
from dashboard.sentiment_analysis import render_sentiment_analysis
# from dashboard.upload_data import render_upload_data
# from dashboard.metrics import render_metrics

# 1. Page Configuration
st.set_page_config(
    page_title="Automobile Demand Intelligence Platform",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Styling Injection
inject_custom_css()

# 3. Initialise data-mode session state and activate the correct DB engine
#    This must happen before any database query so every render function
#    automatically hits the right database.
if "data_mode" not in st.session_state:
    st.session_state.data_mode = "real"

set_data_mode(st.session_state.data_mode)

# 4. Auto-seed real_demand.db on first switch to Real mode
if st.session_state.data_mode == "real":
    from preprocessing.seed_real_database import main as _seed_real
    from database.models import Sale
    _chk_session = get_db_session()
    try:
        _needs_seed = _chk_session.query(Sale).count() == 0
    except Exception:
        _needs_seed = True
    finally:
        _chk_session.close()

    if _needs_seed:
        with st.spinner("First-time setup: seeding Real data source… this takes ~30s"):
            _seed_real()
        st.rerun()

# 5. Fetch unique sidebar filter choices dynamically from DB
session = get_db_session()
try:
    options = get_unique_filter_options(session)
except Exception:
    # Fail-safe fallbacks if DB is not seeded or active
    options = {
        "regions": ["California", "Texas", "Florida", "New York", "Illinois", "Georgia", "Ohio", "Michigan"],
        "cities": [
            "Los Angeles", "San Francisco", "San Diego", "Sacramento",
            "Houston", "Dallas", "Austin", "San Antonio",
            "Miami", "Orlando", "Tampa", "Jacksonville",
            "New York City", "Buffalo", "Albany", "Rochester",
            "Chicago", "Naperville", "Springfield",
            "Atlanta", "Savannah", "Augusta",
            "Columbus", "Cleveland", "Cincinnati",
            "Detroit", "Grand Rapids", "Ann Arbor"
        ],
        "categories": ["SUV", "Sedan", "Luxury", "EV", "Sports Car", "Pickup Truck", "Van/Commercial"],
        "fuel_types": ["Gasoline", "Diesel", "Electric", "Hybrid"],
        "brands": ["Toyota", "Nissan", "Hyundai", "Kia", "Honda", "Mercedes-Benz", "BMW", "Audi", "Lexus", "Ford", "Chevrolet", "Tesla"],
        "years": [2021, 2022, 2023, 2024, 2025, 2026]
    }
finally:
    session.close()

# 6. HEADER BRANDING
# is_real = st.session_state.data_mode == "real"
# mode_badge = (
#     '<span style="background:rgba(16,185,129,0.15);color:#10b981;border:1px solid rgba(16,185,129,0.35);'
#     'border-radius:6px;padding:2px 10px;font-size:12px;font-weight:600;letter-spacing:0.5px;'
#     'vertical-align:middle;margin-left:10px;">REAL DATA</span>'
#     if is_real else
#     '<span style="background:rgba(99,102,241,0.15);color:#818cf8;border:1px solid rgba(99,102,241,0.35);'
#     'border-radius:6px;padding:2px 10px;font-size:12px;font-weight:600;letter-spacing:0.5px;'
#     'vertical-align:middle;margin-left:10px;">TEST DATA</span>'
# )

st.markdown(f"""
    <div style="text-align: center; margin-top: -30px; margin-bottom: 20px;">
        <h1 class="main-title">
            <span class="gradient-text">Automobile Demand Intelligence Platform</span>
        </h1>
        <p style="color: #9ca3af; font-size: 15px; margin-top: -10px;">Enterprise Decision Support Suite — Demand Forecasting & Customer Analytics</p>
    </div>
""", unsafe_allow_html=True)

# 7. SIDEBAR NAVIGATION & GLOBAL FILTERS
with st.sidebar:

    # ── Data Source Toggle (hidden) ─────────────────────────────────────────
    # st.markdown("""
    #     <div style="text-align:center; padding: 6px 0 4px 0;">
    #         <span style="color:#9ca3af; font-size:11px; font-weight:600;
    #                      text-transform:uppercase; letter-spacing:1px;">Data Source</span>
    #     </div>
    # """, unsafe_allow_html=True)

    # st.markdown("""
    #     <style>
    #     /* Style the horizontal radio as a pill-toggle */
    #     div[data-testid="stHorizontalBlock"] div[role="radiogroup"] {
    #         gap: 0 !important;
    #     }
    #     div[data-testid="stHorizontalBlock"] div[role="radiogroup"] label {
    #         flex: 1;
    #         justify-content: center;
    #         border-radius: 0;
    #         padding: 5px 0;
    #         font-size: 13px !important;
    #         font-weight: 600 !important;
    #     }
    #     div[data-testid="stHorizontalBlock"] div[role="radiogroup"] label:first-child {
    #         border-radius: 8px 0 0 8px !important;
    #     }
    #     div[data-testid="stHorizontalBlock"] div[role="radiogroup"] label:last-child {
    #         border-radius: 0 8px 8px 0 !important;
    #     }
    #     </style>
    # """, unsafe_allow_html=True)

    # _mode_choice = st.radio(
    #     "data_source_toggle",
    #     options=["Test", "Real"],
    #     index=0 if st.session_state.data_mode == "test" else 1,
    #     horizontal=True,
    #     label_visibility="collapsed",
    #     key="data_source_radio",
    # )

    # # Persist choice and re-activate engine if the user changed it
    # _new_mode = "test" if _mode_choice == "Test" else "real"
    # if _new_mode != st.session_state.data_mode:
    #     st.session_state.data_mode = _new_mode
    #     set_data_mode(_new_mode)
    #     st.rerun()

    # st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 12px 0;'>", unsafe_allow_html=True)

    # ── Navigation ─────────────────────────────────────────────────────────
    st.markdown("<div style='text-align: center; padding: 4px 0 10px;'>", unsafe_allow_html=True)
    st.image("assets/images/logo.png", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

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
            # "Insights & Simulator",
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
            # "cpu",
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
    st.markdown("<h3 style='color: #f3f4f6; font-size: 15px; margin-bottom: 10px;'>Global Filters</h3>", unsafe_allow_html=True)

    # Global Filters Inputs
    start_date = st.date_input("Start Date", value=date(2021, 1, 1))
    end_date = st.date_input("End Date", value=date(2026, 5, 31))

    region = st.selectbox("State", options=["All"] + options["regions"])

    # Filter cities dynamically based on state
    if region != "All":
        session = get_db_session()
        try:
            from database.models import Sale
            region_cities = [c[0] for c in session.query(Sale.city).filter(Sale.state == region).distinct().all() if c[0]]
            city_options = sorted(region_cities)
        except Exception:
            city_options = options["cities"]
        finally:
            session.close()
    else:
        city_options = options["cities"]

    city = st.selectbox("City", options=["All"] + city_options)
    brand = st.selectbox("Brand", options=["All"] + options["brands"])
    category = st.selectbox("Vehicle Category", options=["All"] + options["categories"])
    fuel_type = st.selectbox("Fuel Type", options=["All"] + options["fuel_types"])

    # Compile global filter dictionary
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "region": None if region == "All" else region,
        "city": None if city == "All" else city,
        "brand": None if brand == "All" else brand,
        "vehicle_category": None if category == "All" else category,
        "fuel_type": None if fuel_type == "All" else fuel_type
    }

# 8. ROUTING MAIN VIEWS
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
# elif selected_page == "Insights & Simulator":
#     render_ai_insights(filters)
elif selected_page == "Sentimental  analysis":
    render_sentiment_analysis(filters)
# elif selected_page == "Data Ingestion Engine":
#     render_upload_data()
# elif selected_page == "Model Performance Metrics":
#     render_metrics()
