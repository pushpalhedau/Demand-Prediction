import streamlit as st
from datetime import date
from streamlit_option_menu import option_menu


# A page's identity is its KEY, never its (language-dependent) label. The
# sidebar nav, the floating top-left tab menu that stays visible when the
# sidebar is collapsed, and the view router at the bottom of this file all
# key off PAGE_KEYS so routing never breaks when someone switches language.
PAGE_KEYS = [
    "tab.overview",
    "tab.forecasting",
    "tab.comparison",
    "tab.regional",
    "tab.customers",
    "tab.inventory",
    "tab.sentiment",
]
PAGE_ICONS = [
    "speedometer2",
    "graph-up-arrow",
    "columns-gap",
    "shop",
    "people",
    "box-seam",
    "chat-left-quote",
]
# Material Symbols equivalents of PAGE_ICONS, for the icon-only nav rail
# (st.button only speaks Material icons, not the Bootstrap set option_menu uses).
PAGE_RAIL_ICONS = [
    "space_dashboard",
    "trending_up",
    "grid_view",
    "storefront",
    "group",
    "inventory_2",
    "forum",
]

from backend.db.connection import get_db_session
from backend.db.models import Sale
from frontend.customer_app.auth import require_login, render_account_menu
from backend.tenancy.capabilities import get_capabilities, tab_available
from backend.repositories.queries import get_unique_filter_options
from frontend.shared.ui import ASSETS_DIR, inject_custom_css
from frontend.shared.i18n import t, tv, language_selector, get_lang
from frontend.customer_app.views.overview import render_overview
from frontend.customer_app.views.forecasting import render_forecasting
from frontend.customer_app.views.comparison import render_comparison
from frontend.customer_app.views.regional import render_regional
from frontend.customer_app.views.customers import render_customers
from frontend.customer_app.views.inventory import render_inventory
# from dashboard.ai_insights import render_ai_insights
from frontend.customer_app.views.sentiment import render_sentiment_analysis
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

# 3. AUTH GATE
#    Nothing below runs for an unauthenticated visitor. A successful login sets
#    st.session_state["tenant_id"], which pins every DB transaction to that
#    tenant (Postgres row-level security), so all queries below are tenant-scoped.
identity = require_login()
caps = get_capabilities()

# Accounts are set up by the operator (admin console). Until their data is loaded there is nothing to show.
if not caps["sales"]:
    with st.sidebar:
        render_account_menu()
    st.markdown("<h2 class='gradient-text'>Your account is being set up</h2>", unsafe_allow_html=True)
    st.info("Your data is being prepared. Your dashboards will appear here as soon as it is ready. "
            "If this takes longer than expected, please contact support.")
    st.stop()

# Show only the tabs this tenant has data for.
_keep = [i for i, k in enumerate(PAGE_KEYS) if tab_available(k, caps)]
PAGE_KEYS = [PAGE_KEYS[i] for i in _keep]
PAGE_ICONS = [PAGE_ICONS[i] for i in _keep]
PAGE_RAIL_ICONS = [PAGE_RAIL_ICONS[i] for i in _keep]
if st.session_state.get("active_page") not in PAGE_KEYS:
    st.session_state["active_page"] = PAGE_KEYS[0]

# 5. Fetch unique sidebar filter choices dynamically from DB
session = get_db_session()
try:
    options = get_unique_filter_options(session)
except Exception:
    options = {"regions": [], "cities": [], "categories": [], "fuel_types": [], "brands": [], "years": []}
finally:
    session.close()

# 6. GLOBAL LANGUAGE TOGGLE
# Pinned to the top-right of the main screen via CSS (div.st-key-lang in
# custom.css). Rendered before the header so every t() call below already
# resolves in the language the user just picked, with no second rerun needed.
language_selector(label_visibility="collapsed")

# 6b. COLLAPSED-SIDEBAR ICON RAIL
# Streamlit's native sidebar collapse works by translating the whole sidebar
# off-screen (transform: translateX(-100%)) rather than removing it — so a
# thin rail rendered at that same left edge, one z-index layer below the
# sidebar (div.st-key-nav_rail in custom.css), sits hidden behind the
# expanded sidebar and is revealed automatically the instant it collapses.
# No Python-side collapse detection needed. Buttons mirror
# st.session_state["active_page"], so the active tab stays visible (icon
# highlighted) and every tab stays one click away regardless of sidebar state.
_page_labels = [t(k) for k in PAGE_KEYS]
with st.container(key="nav_rail"):
    for _pk, _micon, _label in zip(PAGE_KEYS, PAGE_RAIL_ICONS, _page_labels):
        if st.button(
            " ",
            icon=f":material/{_micon}:",
            key=f"railbtn_{_pk}",
            help=_label,
            type="primary" if _pk == st.session_state["active_page"] else "secondary",
        ):
            st.session_state["active_page"] = _pk
            st.rerun()

# 7. HEADER BRANDING
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
            <span class="gradient-text">{t("app.header")}</span>
        </h1>
        <p style="color: #9ca3af; font-size: 15px; margin-top: -10px;">{t("app.header_sub")}</p>
    </div>
""", unsafe_allow_html=True)

# 8. SIDEBAR NAVIGATION & GLOBAL FILTERS
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
    st.image(str(ASSETS_DIR / "images" / "logo.png"), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Sleek sidebar menu with option_menu. manual_select keeps it mirroring
    # st.session_state["active_page"] — shared with the floating top-left tab
    # menu rendered above (visible even when this sidebar is collapsed) —
    # including across the key change that happens when the language toggles.
    selected_label = option_menu(
        menu_title=None,
        options=_page_labels,
        icons=PAGE_ICONS,
        menu_icon="cast",
        manual_select=PAGE_KEYS.index(st.session_state["active_page"]),
        key=f"nav_{get_lang()}",
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
    st.session_state["active_page"] = PAGE_KEYS[_page_labels.index(selected_label)]

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
    st.markdown(f"<h3 style='color: #f3f4f6; font-size: 15px; margin-bottom: 6px;'>{t('app.filters')}</h3>", unsafe_allow_html=True)

    # Global Filters — paired into two columns so the whole block fits the
    # sidebar without a long scroll. Dropdown popovers render at body level, so
    # the compact rows don't clip them.
    _dc1, _dc2 = st.columns(2)
    with _dc1:
        start_date = st.date_input(t("filter.date_from"), value=caps["first_sale"])
    with _dc2:
        end_date = st.date_input(t("filter.date_to"), value=caps["last_sale"])

    _fc1, _fc2 = st.columns(2)
    with _fc1:
        region = st.selectbox(
            t("filter.state"), options=["All"] + options["regions"],
            format_func=lambda v: t("filter.all") if v == "All" else v)

    # Filter areas dynamically based on state
    if region != "All":
        session = get_db_session()
        try:
            from backend.db.models import Sale
            region_cities = [c[0] for c in session.query(Sale.city).filter(Sale.region == region).distinct().all() if c[0]]
            city_options = sorted(region_cities)
        except Exception:
            city_options = options["cities"]
        finally:
            session.close()
    else:
        city_options = options["cities"]

    with _fc2:
        city = st.selectbox(
            t("filter.city"), options=["All"] + city_options,
            format_func=lambda v: t("filter.all") if v == "All" else v)

    _fc3, _fc4 = st.columns(2)
    with _fc3:
        brand = st.selectbox(
            t("filter.brand"), options=["All"] + options["brands"],
            format_func=lambda v: t("filter.all") if v == "All" else v)
    with _fc4:
        category = st.selectbox(
            t("filter.category"), options=["All"] + options["categories"],
            format_func=lambda v: t("filter.all") if v == "All" else tv(v))

    fuel_type = st.selectbox(
        t("filter.fuel"), options=["All"] + options["fuel_types"],
        format_func=lambda v: t("filter.all") if v == "All" else tv(v))

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

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 15px 0;'>", unsafe_allow_html=True)
    render_account_menu()

# 9. ROUTING MAIN VIEWS
selected_page = st.session_state["active_page"]

if selected_page == "tab.overview":
    render_overview(filters)
elif selected_page == "tab.forecasting":
    render_forecasting(filters)
elif selected_page == "tab.comparison":
    render_comparison(filters)
elif selected_page == "tab.regional":
    render_regional(filters)
elif selected_page == "tab.customers":
    render_customers(filters)
elif selected_page == "tab.inventory":
    render_inventory(filters)
# elif selected_page == "Insights & Simulator":
#     render_ai_insights(filters)
elif selected_page == "tab.sentiment":
    render_sentiment_analysis(filters)
# elif selected_page == "Model Performance Metrics":
#     render_metrics()
