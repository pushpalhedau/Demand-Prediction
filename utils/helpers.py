import streamlit as st
import os

def inject_custom_css():
    """
    Inject custom HSL CSS styling from custom.css into Streamlit app.
    """
    css_path = os.path.join("assets", "styles", "custom.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        # Fallback basic styles if file not found
        st.markdown("""
            <style>
            .gradient-text {
                background: linear-gradient(135deg, #a5b4fc 0%, #6366f1 50%, #06b6d4 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 800;
            }
            </style>
        """, unsafe_allow_html=True)

def render_kpi_card(title: str, value: str, delta: str = None, is_positive: bool = True):
    """
    Renders a custom glassmorphic KPI card with delta indicator.
    """
    delta_html = ""
    if delta:
        delta_class = "positive" if is_positive else "negative"
        arrow = "▲" if is_positive else "▼"
        delta_html = f'<div class="kpi-delta {delta_class}">{arrow} {delta}</div>'
        
    card_html = f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

def get_color_palette():
    """
    Return standard premium hex color list for Plotly charts to keep themes harmonized.
    """
    return {
        "primary": "#6366f1",    # Indigo
        "secondary": "#06b6d4",  # Cyan
        "accent": "#ec4899",     # Pink
        "success": "#10b981",    # Emerald
        "warning": "#f59e0b",    # Amber
        "danger": "#ef4444",     # Red
        "muted": "#4b5563",      # Gray
        "colors_seq": ["#6366f1", "#06b6d4", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
    }
