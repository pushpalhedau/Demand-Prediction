"""
Premium dark enterprise theme for UAE Decision Intelligence Platform.
Design language: Palantir AIP / Linear / Vercel — dark, data-dense, precise.
"""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── Reset & Base ──────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    background: #07071a !important;
    color: #e2e8f0 !important;
}

/* ── Hide Streamlit chrome ──────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden !important; }
.stDeployButton { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
.stDecoration { display: none !important; }

/* ── Sidebar ────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #0d0d20 !important;
    border-right: 1px solid #1e1e3f !important;
}
[data-testid="stSidebar"] .stMarkdown p {
    color: #94a3b8 !important;
    font-size: 12px !important;
}
[data-testid="stSidebarNav"] { display: none !important; }

/* ── Tabs ───────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #1e1e3f !important;
    gap: 0 !important;
    padding: 0 8px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748b !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
    padding: 12px 18px !important;
    border-radius: 0 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.15s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #a5b4fc !important;
    background: rgba(99,102,241,0.05) !important;
}
.stTabs [aria-selected="true"] {
    color: #818cf8 !important;
    border-bottom: 2px solid #6366f1 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background: transparent !important;
    padding: 0 !important;
}

/* ── Inputs & Selects ───────────────────────────────────────── */
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background: #111128 !important;
    border: 1px solid #1e1e3f !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    background: #111128 !important;
    border: 1px solid #1e1e3f !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}

/* ── Buttons ────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5, #6366f1) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 10px 20px !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #4338ca, #4f46e5) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.4) !important;
}

/* ── Sliders ────────────────────────────────────────────────── */
.stSlider [data-testid="stTickBar"] { display: none; }
.stSlider [role="slider"] {
    background: #6366f1 !important;
    border: 2px solid #818cf8 !important;
}

/* ── Metrics ────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #111128 !important;
    border: 1px solid #1e1e3f !important;
    border-radius: 12px !important;
    padding: 16px !important;
}
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 12px !important; }
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"]  { font-size: 13px !important; }

/* ── DataFrames ─────────────────────────────────────────────── */
.stDataFrame { background: transparent !important; }
.stDataFrame thead tr th {
    background: #111128 !important;
    color: #64748b !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    border-bottom: 1px solid #1e1e3f !important;
}
.stDataFrame tbody tr td {
    background: #0d0d20 !important;
    color: #e2e8f0 !important;
    border-bottom: 1px solid #0f0f28 !important;
}
.stDataFrame tbody tr:hover td { background: rgba(99,102,241,0.06) !important; }

/* ── Expander ────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: #111128 !important;
    border: 1px solid #1e1e3f !important;
    border-radius: 8px !important;
    color: #a5b4fc !important;
    font-weight: 500 !important;
}
.streamlit-expanderContent {
    background: #0d0d20 !important;
    border: 1px solid #1e1e3f !important;
    border-top: none !important;
}

/* ── Loading: kill Streamlit's page-wide fade during rerun ─── */
.stale {
    opacity: 1 !important;
    transition: none !important;
    filter: none !important;
}

/* ── Global instant loader overlay ──────────────────────────── */
#dp-loader {
    position: fixed;
    inset: 0;
    background: rgba(7,7,26,0.88);
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
    opacity: 1;
    transition: opacity 0.15s ease;
    pointer-events: none;
}

#dp-loader::after {
    content: '';
    width: 42px;
    height: 42px;
    border: 3px solid rgba(99,102,241,0.15);
    border-top-color: #6366f1;
    border-right-color: rgba(99,102,241,0.5);
    border-radius: 50%;
    animation: dp-spin 0.7s cubic-bezier(0.55,0,0.45,1) infinite;
}

@keyframes dp-spin {
    to { transform: rotate(360deg); }
}

/* ── Spinner card ────────────────────────────────────────────── */
[data-testid="stSpinner"] {
    background: rgba(17,17,40,0.97) !important;
    border: 1px solid #1e1e3f !important;
    border-radius: 12px !important;
    padding: 14px 20px !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 12px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(99,102,241,0.08) !important;
    backdrop-filter: blur(12px) !important;
    margin: 4px 0 !important;
}

/* Spinner ring — gradient arc look */
.stSpinner > div {
    width: 22px !important;
    height: 22px !important;
    border-width: 2.5px !important;
    border-style: solid !important;
    border-color: rgba(99,102,241,0.15) !important;
    border-top-color: #6366f1 !important;
    border-right-color: rgba(99,102,241,0.5) !important;
    border-radius: 50% !important;
    animation: dp-spin 0.7s cubic-bezier(0.55,0,0.45,1) infinite !important;
    background: none !important;
    flex-shrink: 0 !important;
}

@keyframes dp-spin {
    to { transform: rotate(360deg); }
}

/* Hide spinner label — ring only */
[data-testid="stSpinner"] p,
[data-testid="stSpinner"] small p,
[data-testid="stSpinner"] span {
    display: none !important;
}

/* ── Progress Bar ────────────────────────────────────────────── */
.stProgress > div > div { background: #6366f1 !important; }

/* ── Divider ────────────────────────────────────────────────── */
hr { border-color: #1e1e3f !important; }

/* ── Scrollbar ──────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #07071a; }
::-webkit-scrollbar-thumb { background: #2d2d5e; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4f46e5; }
</style>
"""

PLOTLY_DARK_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor":  "rgba(0,0,0,0)",
        "font":          {"family": "Inter, sans-serif", "color": "#94a3b8", "size": 12},
        "title":         {"text": "", "font": {"color": "#f1f5f9", "size": 16, "family": "Inter"}, "x": 0.02},
        "xaxis": {
            "gridcolor": "#1e1e3f", "gridwidth": 1,
            "linecolor": "#1e1e3f", "tickcolor": "#1e1e3f",
            "tickfont": {"color": "#64748b", "size": 11},
            "zeroline": False,
        },
        "yaxis": {
            "gridcolor": "#1e1e3f", "gridwidth": 1,
            "linecolor": "#1e1e3f", "tickcolor": "#1e1e3f",
            "tickfont": {"color": "#64748b", "size": 11},
            "zeroline": False,
        },
        "legend": {
            "bgcolor": "rgba(13,13,32,0.8)", "bordercolor": "#1e1e3f",
            "borderwidth": 1, "font": {"color": "#94a3b8", "size": 11},
        },
        "hoverlabel": {
            "bgcolor": "#111128", "bordercolor": "#6366f1",
            "font": {"color": "#f1f5f9", "size": 12},
        },
        "margin": {"l": 50, "r": 20, "t": 50, "b": 40},
        "colorway": ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
                     "#06b6d4", "#f97316", "#ec4899", "#84cc16", "#14b8a6"],
    }
}

def themed(**overrides) -> dict:
    """
    Return a layout dict = PLOTLY_DARK_TEMPLATE merged with caller overrides.
    Use instead of **PLOTLY_DARK_TEMPLATE["layout"] to avoid duplicate-key errors
    when passing title=, yaxis=, xaxis=, legend=, etc.

    Example:
        fig.update_layout(**themed(title="My Chart", height=400, yaxis_title="AED"))
    """
    base = dict(PLOTLY_DARK_TEMPLATE["layout"])
    base.update(overrides)
    return base


# Brand colours
C_INDIGO   = "#6366f1"
C_EMERALD  = "#10b981"
C_AMBER    = "#f59e0b"
C_RED      = "#ef4444"
C_VIOLET   = "#8b5cf6"
C_CYAN     = "#06b6d4"
C_SURFACE  = "#111128"
C_BORDER   = "#1e1e3f"
C_TEXT     = "#e2e8f0"
C_SUBTEXT  = "#64748b"
C_BG       = "#07071a"

LOADER_SCRIPT = """
<script>
(function () {
    var overlay = null;
    var removeTimer = null;
    var prevStale = false;

    function show() {
        if (overlay) return;
        clearTimeout(removeTimer);
        overlay = document.createElement('div');
        overlay.id = 'dp-loader';
        document.body.appendChild(overlay);
    }

    function hide() {
        clearTimeout(removeTimer);
        removeTimer = setTimeout(function () {
            if (!overlay) return;
            overlay.style.opacity = '0';
            var el = overlay;
            setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 160);
            overlay = null;
        }, 80);
    }

    // Hook all [data-baseweb="tab"] buttons for an instant response on click
    function hookTabs() {
        document.querySelectorAll('[data-baseweb="tab"]').forEach(function (t) {
            if (t._dpHooked) return;
            t._dpHooked = true;
            t.addEventListener('mousedown', show);
        });
    }

    // Also catch sidebar filter changes and button clicks via the stale mechanism
    var staleObs = new MutationObserver(function () {
        var stale = !!document.querySelector('.stale');
        if (stale && !prevStale) { prevStale = true; show(); }
        else if (!stale && prevStale) { prevStale = false; hide(); }
    });
    staleObs.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] });

    // Re-hook whenever Streamlit re-renders new tab buttons into the DOM
    var hookTimer;
    var domObs = new MutationObserver(function () {
        clearTimeout(hookTimer);
        hookTimer = setTimeout(hookTabs, 300);
    });
    domObs.observe(document.body, { childList: true, subtree: true });

    hookTabs();
})();
</script>
"""
