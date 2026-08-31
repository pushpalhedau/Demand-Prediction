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


# ─────────────────────────────────────────────────────────────────────────────
# Shared glance-first chart system.
#
# Promoted here from dashboard/overview.py so the Executive Overview and Demand
# Forecasting tabs read as one system without copy-paste. Conventions:
#   - one hue per job (history is grey, the forecast is indigo, up/down are
#     green/red), never a rainbow;
#   - direct labels on the mark instead of making the reader trace an axis;
#   - a one-line caption under every chart header (see _section).
# ─────────────────────────────────────────────────────────────────────────────

FONT = "Plus Jakarta Sans"

_INK = "#f3f4f6"          # primary text on the dark canvas
_INK_MUTED = "#9ca3af"    # captions, secondary labels
_GRID = "rgba(255,255,255,0.06)"

_HUE_HISTORY = "#9ca3af"          # actuals / "what already happened"
_HUE_FORECAST = "#6366f1"         # the expected projection
_HUE_BAND = "rgba(99,102,241,0.14)"  # confidence range fill
_HUE_UP = "#10b981"               # favourable / ahead
_HUE_DOWN = "#ef4444"             # unfavourable / behind
_HUE_MARKER = "#f59e0b"           # "forecast starts here" separators


def _fmt_money(value: float) -> str:
    """Compact USD for KPI cards and labels: $3.04B / $742.0M / $940K."""
    value = float(value or 0)
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _compact(n: float) -> str:
    """Compact count for headline numbers and direct labels: 9.4K / 1.2M / 320."""
    n = float(n or 0)
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 10_000:
        return f"{n / 1_000:.0f}K"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,.0f}"


def _pct_label(value, digits: int = 0) -> str:
    """Signed percent with an explicit + / − and a real minus glyph: +8% / −3%."""
    if value is None:
        return "n/a"
    s = f"{abs(value):.{digits}f}%"
    if value > 0:
        return f"+{s}"
    if value < 0:
        return f"−{s}"
    return s


def _section(title: str, caption: str = None):
    """A chart header plus the one-line caption that explains what it shows."""
    st.markdown(f"### {title}")
    if caption:
        st.markdown(
            f"<div style='color:{_INK_MUTED};font-size:12px;margin:-6px 0 12px 0;'>{caption}</div>",
            unsafe_allow_html=True,
        )


def _base_layout(height: int = 340, legend: bool = False, **overrides) -> dict:
    """Common Plotly layout so every figure on these tabs matches."""
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_INK, family=FONT, size=12),
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(showgrid=True, gridcolor=_GRID, title=""),
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        showlegend=legend,
    )
    if legend:
        layout["legend"] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        )
    layout.update(overrides)
    return layout
