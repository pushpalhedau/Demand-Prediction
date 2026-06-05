"""
Premium KPI card components rendered as HTML/CSS via st.markdown.
"""
from __future__ import annotations

import streamlit as st
from typing import Optional


def kpi_card(label: str, value: str, change_pct: Optional[float] = None,
             icon: str = "", suffix: str = "", prefix: str = "",
             gradient: str = "indigo") -> str:
    gradients = {
        "indigo":  "linear-gradient(135deg, #312e81, #4338ca)",
        "emerald": "linear-gradient(135deg, #064e3b, #065f46)",
        "amber":   "linear-gradient(135deg, #78350f, #92400e)",
        "violet":  "linear-gradient(135deg, #4c1d95, #5b21b6)",
        "cyan":    "linear-gradient(135deg, #164e63, #155e75)",
        "rose":    "linear-gradient(135deg, #881337, #9f1239)",
    }
    bar_colors = {
        "indigo": "#6366f1", "emerald": "#10b981", "amber": "#f59e0b",
        "violet": "#8b5cf6", "cyan": "#06b6d4", "rose": "#f43f5e",
    }
    bg = gradients.get(gradient, gradients["indigo"])
    bar = bar_colors.get(gradient, "#6366f1")

    change_html = ""
    if change_pct is not None:
        if change_pct > 0:
            change_html = f'<div class="kpi-change kpi-up">▲ {change_pct:+.1f}% vs prev year</div>'
        elif change_pct < 0:
            change_html = f'<div class="kpi-change kpi-down">▼ {change_pct:.1f}% vs prev year</div>'
        else:
            change_html = f'<div class="kpi-change kpi-neutral">→ Unchanged</div>'

    return f"""
<div class="kpi-card" style="background:{bg}">
  <div class="kpi-bar" style="background:{bar}"></div>
  <div class="kpi-icon">{icon}</div>
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{prefix}{value}{suffix}</div>
  {change_html}
</div>
"""


def render_kpi_row(cards: list[str], cols: int = 4):
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    html = f'<div class="kpi-grid kpi-grid-{cols}">' + "".join(cards) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def alert_card(title: str, description: str, severity: str = "warning",
               action: str = "") -> str:
    colors = {
        "critical": ("#ef4444", "rgba(239,68,68,0.1)"),
        "high":     ("#ef4444", "rgba(239,68,68,0.08)"),
        "warning":  ("#f59e0b", "rgba(245,158,11,0.1)"),
        "medium":   ("#f59e0b", "rgba(245,158,11,0.08)"),
        "info":     ("#6366f1", "rgba(99,102,241,0.1)"),
        "low":      ("#10b981", "rgba(16,185,129,0.1)"),
        "success":  ("#10b981", "rgba(16,185,129,0.1)"),
    }
    icons = {
        "critical": "🔴", "high": "🔴", "warning": "🟡",
        "medium": "🟡", "info": "🔵", "low": "🟢", "success": "🟢",
    }
    border_color, bg = colors.get(severity, colors["info"])
    icon = icons.get(severity, "ℹ️")
    action_html = f'<div class="alert-action">→ {action}</div>' if action else ""
    return f"""
<div class="alert-card" style="border-left-color:{border_color};background:{bg}">
  <span class="alert-icon">{icon}</span>
  <div>
    <div class="alert-title">{title}</div>
    <div class="alert-desc">{description}</div>
    {action_html}
  </div>
</div>
"""


def ai_insight_panel(text: str, title: str = "AI Strategic Insight") -> str:
    return f"""
<div class="ai-panel">
  <div class="ai-panel-header">
    <span class="ai-badge">AI</span>
    <span class="ai-panel-title">{title}</span>
  </div>
  <div class="ai-panel-body">{text}</div>
</div>
"""


def section_header(title: str, subtitle: str = "") -> str:
    sub = f'<div class="sh-subtitle">{subtitle}</div>' if subtitle else ""
    return f'<div class="section-header"><div class="sh-title">{title}</div>{sub}</div>'


def score_badge(score: float, label: str = "", size: str = "md") -> str:
    if score >= 75:
        color = "#10b981"
    elif score >= 50:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    fs = "2.5rem" if size == "lg" else "1.8rem"
    return f"""
<div style="text-align:center">
  <div style="font-size:{fs};font-weight:900;
              background:linear-gradient(135deg,{color},{color}aa);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent">
    {score:.0f}
  </div>
  {f'<div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.1em">{label}</div>' if label else ''}
</div>
"""


KPI_CSS = """
<style>
.kpi-grid { display: grid; gap: 14px; margin: 16px 0; }
.kpi-grid-4 { grid-template-columns: repeat(4, 1fr); }
.kpi-grid-3 { grid-template-columns: repeat(3, 1fr); }
.kpi-grid-2 { grid-template-columns: repeat(2, 1fr); }

.kpi-card {
  border-radius: 14px;
  padding: 20px 20px 16px;
  position: relative;
  overflow: hidden;
  transition: transform .2s, box-shadow .2s;
  border: 1px solid rgba(255,255,255,0.06);
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.kpi-bar {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  border-radius: 14px 14px 0 0;
}
.kpi-icon  { font-size: 20px; margin-bottom: 8px; opacity: .85; }
.kpi-label { font-size: 11px; font-weight: 600; text-transform: uppercase;
             letter-spacing: .1em; color: rgba(255,255,255,.5); margin-bottom: 6px; }
.kpi-value { font-size: 26px; font-weight: 800; color: #f1f5f9; line-height: 1.1; }
.kpi-change { font-size: 12px; font-weight: 600; margin-top: 8px; }
.kpi-up     { color: #34d399; }
.kpi-down   { color: #f87171; }
.kpi-neutral{ color: #fbbf24; }

.alert-card {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 16px; border-radius: 10px; margin: 6px 0;
  border-left: 3px solid;
}
.alert-icon  { font-size: 16px; margin-top: 1px; }
.alert-title { font-size: 13px; font-weight: 600; color: #f1f5f9; margin-bottom: 3px; }
.alert-desc  { font-size: 12px; color: #94a3b8; line-height: 1.5; }
.alert-action{ font-size: 11px; color: #818cf8; margin-top: 5px; font-weight: 500; }

.ai-panel {
  background: linear-gradient(135deg, #0f0f2e, #111128);
  border: 1px solid #3730a3; border-radius: 14px;
  padding: 20px; margin: 12px 0;
}
.ai-panel-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.ai-badge {
  background: #3730a3; color: #a5b4fc;
  font-size: 9px; font-weight: 800; text-transform: uppercase;
  letter-spacing: .15em; padding: 3px 8px; border-radius: 100px;
}
.ai-panel-title { font-size: 13px; font-weight: 600; color: #c7d2fe; }
.ai-panel-body  { font-size: 14px; color: #a5b4fc; line-height: 1.75; }

.section-header { margin: 24px 0 14px; }
.sh-title   { font-size: 17px; font-weight: 700; color: #f1f5f9; }
.sh-subtitle{ font-size: 12px; color: #64748b; margin-top: 3px; }
</style>
"""
