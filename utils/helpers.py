import streamlit as st
import os


def inject_custom_css():
    css_path = os.path.join("assets", "styles", "custom.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
            .gradient-text {
                background: linear-gradient(135deg, #10b981 0%, #f59e0b 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 800;
            }
            </style>
        """, unsafe_allow_html=True)


def render_kpi_card(title: str, value: str, delta: str = None, is_positive: bool = True, icon: str = "", invert_arrow: bool = False):
    delta_html = ""
    if delta:
        cls = "positive" if is_positive else "negative"
        if invert_arrow:
            arrow = "-" if is_positive else "+"
        else:
            arrow = "+" if is_positive else "-"
        delta_html = f'<div class="kpi-delta {cls}">{arrow} {delta}</div>'

    icon_html = f'<div class="kpi-icon">{icon}</div>' if icon else ""

    st.markdown(
        f'<div class="kpi-card">{icon_html}'
        f'<div class="kpi-title">{title}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def fmt_aed(value: float) -> str:
    """Format AED value with appropriate suffix (B/M/K)."""
    if value is None:
        return "—"
    if value >= 1e9:
        return f"AED {value / 1e9:.2f}B"
    if value >= 1e6:
        return f"AED {value / 1e6:.2f}M"
    if value >= 1e3:
        return f"AED {value / 1e3:.1f}K"
    return f"AED {value:,.0f}"



def fmt_number(value, suffix=""):
    if value is None:
        return "—"
    if value >= 1e9:
        return f"{value / 1e9:.2f}B{suffix}"
    if value >= 1e6:
        return f"{value / 1e6:.2f}M{suffix}"
    if value >= 1e3:
        return f"{value / 1e3:.1f}K{suffix}"
    return f"{value:,.0f}{suffix}"


def get_re_colors() -> dict:
    return {
        "primary": "#10b981",    # Emerald
        "gold": "#f59e0b",       # Amber
        "indigo": "#6366f1",     # Indigo
        "cyan": "#06b6d4",       # Cyan
        "rose": "#f43f5e",       # Rose
        "purple": "#8b5cf6",     # Purple
        "sky": "#0ea5e9",        # Sky
        "success": "#22c55e",    # Green
        "danger": "#ef4444",     # Red
        "warning": "#f59e0b",    # Amber
        "muted": "#4b5563",      # Gray
        "colors_seq": [
            "#10b981", "#f59e0b", "#6366f1", "#06b6d4",
            "#f43f5e", "#8b5cf6", "#0ea5e9", "#22c55e",
        ],
        "property_category": {
            "Affordable": "#22c55e",
            "Mid-Market": "#06b6d4",
            "Premium": "#6366f1",
            "Luxury": "#f59e0b",
            "Ultra-Luxury": "#f43f5e",
        },
        "city": {
            "Dubai": "#10b981",
            "Abu Dhabi": "#f59e0b",
            "Sharjah": "#6366f1",
            "Ras Al Khaimah": "#06b6d4",
            "Ajman": "#f43f5e",
            "Fujairah": "#8b5cf6",
            "Umm Al Quwain": "#0ea5e9",
        },
    }


def plotly_dark_layout(title: str = "", height: int = 400) -> dict:
    """Standard dark layout config for all Plotly charts."""
    return dict(
        title=dict(text=title, font=dict(family="Outfit", size=15, color="#f0f4f8"), x=0.01),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color="#94a3b8", size=12),
        height=height,
        margin=dict(l=12, r=12, t=40, b=12),
        legend=dict(
            bgcolor="rgba(10,18,35,0.6)",
            bordercolor="rgba(255,255,255,0.07)",
            borderwidth=1,
            font=dict(size=11, color="#94a3b8"),
        ),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.04)",
            linecolor="rgba(255,255,255,0.08)",
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.04)",
            linecolor="rgba(255,255,255,0.08)",
            tickfont=dict(size=11),
        ),
    )


def section_header(title: str, badge: str = "", icon: str = ""):
    icon_span = f"<span style='margin-right:6px'>{icon}</span>" if icon else ""
    badge_span = (
        f'<span class="section-badge" style="margin-left:8px">{badge}</span>'
        if badge else ""
    )
    st.markdown(f"""
    <div class="section-header">
        <span class="section-title">{icon_span}{title}</span>
        {badge_span}
    </div>
    """, unsafe_allow_html=True)
