"""
Premium KPI card components rendered as HTML/CSS via st.markdown.
"""
from __future__ import annotations

import streamlit as st
from typing import Optional


def kpi_card(label: str, value: str, change_pct: Optional[float] = None,
             icon: str = "", suffix: str = "", prefix: str = "",
             gradient: str = "indigo", help_text: str = "") -> str:
    gradients = {
        "indigo":  "linear-gradient(135deg, #312e81, #4338ca)",
        "emerald": "linear-gradient(135deg, #064e3b, #065f46)",
        "amber":   "linear-gradient(135deg, #78350f, #92400e)",
        "violet":  "linear-gradient(135deg, #4c1d95, #5b21b6)",
        "cyan":    "linear-gradient(135deg, #164e63, #155e75)",
        "rose":    "linear-gradient(135deg, #881337, #9f1239)",
    }
    bg = gradients.get(gradient, gradients["indigo"])

    change_html = ""
    if change_pct is not None:
        if change_pct > 0:
            change_html = f'<div class="kpi-change kpi-up">▲ {change_pct:+.1f}% vs prev year</div>'
        elif change_pct < 0:
            change_html = f'<div class="kpi-change kpi-down">▼ {change_pct:.1f}% vs prev year</div>'
        else:
            change_html = f'<div class="kpi-change kpi-neutral">→ Unchanged</div>'

    info_html = (
        f'<div class="kpi-info-wrap">'
        f'<span class="kpi-info-icon">?</span>'
        f'<div class="kpi-info-tip">{help_text}</div>'
        f'</div>'
    ) if help_text else ""

    return f"""
<div class="kpi-card" style="background:{bg}">
  <div class="kpi-label-row">
    <span class="kpi-label">{label}</span>
    {info_html}
  </div>
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
        "critical": "!!", "high": "!!", "warning": "!",
        "medium": "!", "info": "i", "low": "", "success": "",
    }
    border_color, bg = colors.get(severity, colors["info"])
    icon = icons.get(severity, "i")
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


def section_header(title: str, subtitle: str = "", help_text: str = "") -> str:
    sub = f'<div class="sh-subtitle">{subtitle}</div>' if subtitle else ""
    info_html = (
        f'<div class="sh-info-wrap">'
        f'<span class="sh-info-icon">i</span>'
        f'<div class="sh-info-tip">{help_text}</div>'
        f'</div>'
    ) if help_text else ""
    return (
        f'<div class="section-header">'
        f'<div class="sh-title-row"><div class="sh-title">{title}</div>{info_html}</div>'
        f'{sub}</div>'
    )


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
.kpi-grid { display: grid; gap: 14px; margin: 16px 0; overflow: visible; }
.kpi-grid-4 { grid-template-columns: repeat(4, 1fr); }
.kpi-grid-3 { grid-template-columns: repeat(3, 1fr); }
.kpi-grid-2 { grid-template-columns: repeat(2, 1fr); }

.kpi-card {
  border-radius: 14px;
  padding: 20px 20px 16px;
  position: relative;
  overflow: visible;
  border: 1px solid rgba(255,255,255,0.06);
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.kpi-label-row {
  display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
}
.kpi-label {
  font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.55);
  line-height: 1.3; text-transform: uppercase; letter-spacing: 0.07em;
}
.kpi-value {
  font-size: 28px; font-weight: 800; color: #f1f5f9; line-height: 1.15;
}
.kpi-change { font-size: 12px; font-weight: 600; margin-top: 8px; }
.kpi-up     { color: #34d399; }
.kpi-down   { color: #f87171; }
.kpi-neutral{ color: #fbbf24; }

/* ── Info icon — KPI card ───────────────────────────────────── */
.kpi-info-wrap {
  position: relative; display: inline-flex; align-items: center;
  flex-shrink: 0;
}
.kpi-info-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 15px; height: 15px; border-radius: 50%;
  background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.5);
  font-size: 9px; font-weight: 700;
  cursor: help; border: 1px solid rgba(255,255,255,0.18);
  font-family: Georgia, serif; transition: all 0.15s; line-height: 1;
}
.kpi-info-wrap:hover .kpi-info-icon {
  background: rgba(255,255,255,0.2); color: #fff;
  border-color: rgba(255,255,255,0.4);
}
.kpi-info-tip {
  visibility: hidden; opacity: 0;
  position: absolute; left: 0; top: calc(100% + 6px);
  width: 215px; background: #111128;
  border: 1px solid #3730a3; border-radius: 8px;
  padding: 9px 11px; font-size: 11px; color: #a5b4fc;
  line-height: 1.55; box-shadow: 0 8px 32px rgba(0,0,0,0.55);
  z-index: 99999; transition: opacity 0.15s; pointer-events: none;
  font-style: normal; font-weight: 400;
}
.kpi-info-wrap:hover .kpi-info-tip { visibility: visible; opacity: 1; }

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
.sh-title-row { display: flex; align-items: center; }
.sh-title   { font-size: 17px; font-weight: 700; color: #f1f5f9; }
.sh-subtitle{ font-size: 12px; color: #64748b; margin-top: 3px; }

/* ── Info icon — section header ─────────────────────────────── */
.sh-info-wrap {
  position: relative; display: inline-flex;
  align-items: center; margin-left: 8px;
}
.sh-info-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 15px; height: 15px; border-radius: 50%;
  background: rgba(99,102,241,0.12); color: #818cf8;
  font-size: 9px; font-weight: 700; font-style: italic;
  cursor: help; border: 1px solid rgba(99,102,241,0.22);
  font-family: Georgia, serif; transition: all 0.15s; line-height: 1;
}
.sh-info-wrap:hover .sh-info-icon {
  background: rgba(99,102,241,0.28); color: #c7d2fe;
  border-color: rgba(99,102,241,0.5);
}
.sh-info-tip {
  visibility: hidden; opacity: 0;
  position: absolute; left: 0; top: calc(100% + 6px);
  width: 255px; background: #111128;
  border: 1px solid #3730a3; border-radius: 8px;
  padding: 9px 12px; font-size: 11px; color: #a5b4fc;
  line-height: 1.55; box-shadow: 0 8px 32px rgba(0,0,0,0.55);
  z-index: 99999; transition: opacity 0.15s; pointer-events: none;
  font-style: normal; font-weight: 400;
}
.sh-info-wrap:hover .sh-info-tip { visibility: visible; opacity: 1; }
</style>
"""
