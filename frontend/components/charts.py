"""
Reusable Plotly chart builders using the platform dark theme.
All update_layout calls use themed(**kwargs) to avoid duplicate-key errors.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any
import pandas as pd
import plotly.graph_objects as go

from frontend.components.theme import themed, C_INDIGO, C_EMERALD, C_AMBER, C_RED


def forecast_chart(historical: Dict, forecast: Dict, title: str = "Demand Forecast",
                    unit: str = "Units", height: int = 420) -> go.Figure:
    fig = go.Figure()

    hist_dates  = historical.get("dates", [])
    hist_values = historical.get("values", [])
    fc_dates    = forecast.get("dates", [])
    fc_values   = forecast.get("values", [])
    fc_lower    = forecast.get("lower", fc_values)
    fc_upper    = forecast.get("upper", fc_values)

    # Subtle gradient fill under historical
    if hist_dates and hist_values:
        fig.add_trace(go.Scatter(
            x=hist_dates, y=hist_values,
            fill="tozeroy",
            fillcolor="rgba(99,102,241,0.08)",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Historical line
    fig.add_trace(go.Scatter(
        x=hist_dates, y=hist_values,
        name="Historical",
        line=dict(color=C_INDIGO, width=2.5),
        mode="lines",
        hovertemplate="<b>%{y:,.0f}</b><extra>Historical</extra>",
    ))

    if fc_dates and fc_values:
        # Confidence band with visible border
        fig.add_trace(go.Scatter(
            x=fc_dates + fc_dates[::-1],
            y=fc_upper + fc_lower[::-1],
            fill="toself",
            fillcolor="rgba(16,185,129,0.10)",
            line=dict(color="rgba(16,185,129,0.22)", width=0.8),
            showlegend=True,
            name="90% CI",
            hoverinfo="skip",
        ))

        # Forecast line
        fig.add_trace(go.Scatter(
            x=fc_dates, y=fc_values,
            name="Forecast",
            line=dict(color=C_EMERALD, width=2.5, dash="dash"),
            mode="lines",
            hovertemplate="<b>%{y:,.0f}</b><extra>Forecast</extra>",
        ))

        # Vertical separator at forecast start (add_shape handles date strings correctly)
        fig.add_shape(
            type="line",
            x0=fc_dates[0], x1=fc_dates[0],
            y0=0, y1=1, yref="paper",
            line=dict(color="rgba(148,163,184,0.3)", width=1.5, dash="dot"),
        )
        fig.add_annotation(
            x=fc_dates[0], y=0.98, yref="paper",
            text="Forecast →",
            showarrow=False,
            font=dict(color="#64748b", size=10, family="Inter, sans-serif"),
            xanchor="left", yanchor="top",
        )

    fig.update_layout(**themed(
        height=height,
        title=title,
        yaxis_title=unit,
        xaxis_title="",
        hovermode="x unified",
        yaxis_tickformat=",",
        legend_orientation="h",
        legend_yanchor="bottom",
        legend_y=1.02,
        legend_xanchor="right",
        legend_x=1,
        margin_l=60,
        margin_r=20,
        margin_t=60,
        margin_b=40,
    ))
    return fig


def bar_chart(labels: List, values: List, title: str = "",
              color: str = C_INDIGO, height: int = 340,
              horizontal: bool = False, value_format: str = "") -> go.Figure:
    if horizontal:
        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=color,
            text=[f"{v:,.0f}{value_format}" for v in values],
            textposition="outside", textfont=dict(color="#94a3b8", size=11),
        ))
    else:
        fig = go.Figure(go.Bar(
            x=labels, y=values, marker_color=color,
            text=[f"{v:,.0f}{value_format}" for v in values],
            textposition="outside", textfont=dict(color="#94a3b8", size=11),
        ))
    fig.update_layout(**themed(height=height, title=title, showlegend=False, bargap=0.3))
    return fig


def line_chart(df: pd.DataFrame, x: str, y: str | List[str], title: str = "",
               height: int = 340, color_map: Optional[Dict] = None) -> go.Figure:
    colors = [C_INDIGO, C_EMERALD, C_AMBER, C_RED, "#8b5cf6", "#06b6d4"]
    fig = go.Figure()
    ys = [y] if isinstance(y, str) else y
    for i, col in enumerate(ys):
        c = colors[i % len(colors)] if not color_map else color_map.get(col, colors[i])
        fig.add_trace(go.Scatter(x=df[x], y=df[col], name=col,
                                  line=dict(color=c, width=2), mode="lines"))
    fig.update_layout(**themed(height=height, title=title))
    return fig


def area_chart(x: List, y: List, title: str = "", color: str = C_INDIGO,
               height: int = 300) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=x, y=y, fill="tozeroy",
        line=dict(color=color, width=2),
        fillcolor=f"rgba({_hex_to_rgb(color)},0.15)",
    ))
    fig.update_layout(**themed(height=height, title=title))
    return fig


def pie_chart(labels: List, values: List, title: str = "", height: int = 320,
              hole: float = 0.55) -> go.Figure:
    colors = [C_INDIGO, C_EMERALD, C_AMBER, "#8b5cf6", "#06b6d4", "#f97316",
              "#ec4899", C_RED, "#84cc16", "#14b8a6"]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=hole,
        marker=dict(colors=colors[:len(labels)], line=dict(color="#07071a", width=2)),
        textfont=dict(color="#94a3b8", size=12),
    ))
    fig.update_layout(**themed(height=height, title=title, showlegend=True))
    return fig


def scatter_chart(df: pd.DataFrame, x: str, y: str, color: Optional[str] = None,
                   size: Optional[str] = None, text: Optional[str] = None,
                   title: str = "", height: int = 420) -> go.Figure:
    kw: Dict[str, Any] = dict(x=df[x], y=df[y], mode="markers")
    if text and text in df.columns:
        kw["text"] = df[text]
        kw["mode"] = "markers+text"
        kw["textposition"] = "top center"
        kw["textfont"]     = dict(color="#94a3b8", size=10)
    if size and size in df.columns:
        kw["marker"] = dict(
            size=df[size].clip(lower=4, upper=30).fillna(8),
            color=df[color] if color and color in df.columns else C_INDIGO,
            colorscale="Viridis", showscale=bool(color),
            line=dict(color="#07071a", width=1),
        )
    else:
        kw["marker"] = dict(color=C_INDIGO, size=8, line=dict(color="#07071a", width=1))
    fig = go.Figure(go.Scatter(**kw))
    fig.update_layout(**themed(height=height, title=title))
    return fig


def heatmap_chart(df_pivot: pd.DataFrame, title: str = "", height: int = 400,
                   colorscale: str = "Viridis") -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=df_pivot.values.tolist(),
        x=df_pivot.columns.tolist(),
        y=df_pivot.index.tolist(),
        colorscale=colorscale,
        showscale=True,
        hoverongaps=False,
    ))
    fig.update_layout(**themed(height=height, title=title))
    return fig


def gauge_chart(value: float, title: str = "", min_val: float = 0, max_val: float = 100,
                thresholds: Optional[List[float]] = None, height: int = 260) -> go.Figure:
    if thresholds is None:
        thresholds = [33, 66]
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"color": "#94a3b8", "size": 13}},
        number={"font": {"color": "#f1f5f9", "size": 32, "family": "Inter"}},
        gauge=dict(
            axis=dict(range=[min_val, max_val], tickcolor="#1e1e3f",
                      tickfont=dict(color="#64748b", size=10)),
            bar=dict(color=C_INDIGO),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=1, bordercolor="#1e1e3f",
            steps=[
                dict(range=[min_val, thresholds[0]], color="rgba(239,68,68,0.2)"),
                dict(range=[thresholds[0], thresholds[1]], color="rgba(245,158,11,0.2)"),
                dict(range=[thresholds[1], max_val], color="rgba(16,185,129,0.2)"),
            ],
        ),
    ))
    fig.update_layout(**themed(height=height))
    return fig


def monte_carlo_chart(mc_result: Dict, metric: str = "demand", height: int = 400) -> go.Figure:
    paths  = mc_result.get(f"{metric}_paths", {})
    months = list(range(1, mc_result.get("horizon_months", 12) + 1))

    fig = go.Figure()
    if "p10" in paths and "p90" in paths:
        fig.add_trace(go.Scatter(
            x=months + months[::-1],
            y=paths["p90"] + paths["p10"][::-1],
            fill="toself", fillcolor="rgba(99,102,241,0.1)",
            line=dict(color="rgba(0,0,0,0)"), name="P10-P90 Band", showlegend=True,
        ))
    if "p25" in paths and "p75" in paths:
        fig.add_trace(go.Scatter(
            x=months + months[::-1],
            y=paths["p75"] + paths["p25"][::-1],
            fill="toself", fillcolor="rgba(99,102,241,0.2)",
            line=dict(color="rgba(0,0,0,0)"), name="P25-P75 Band", showlegend=True,
        ))
    if "p50" in paths:
        fig.add_trace(go.Scatter(
            x=months, y=paths["p50"],
            name="Median (P50)", line=dict(color=C_EMERALD, width=2.5),
        ))
    fig.update_layout(**themed(
        height=height,
        title=f"Monte Carlo Simulation — {metric.title()}",
        xaxis_title="Months",
        hovermode="x unified",
    ))
    return fig


def feature_importance_chart(features: List[Dict], height: int = 360) -> go.Figure:
    if not features:
        return go.Figure()
    labels = [f.get("label", f.get("feature", "")) for f in features]
    values = [f.get("importance_pct", f.get("importance", 0)) for f in features]
    colors = [C_EMERALD if f.get("direction") == "positive" else C_RED for f in features]
    fig = go.Figure(go.Bar(
        x=values[::-1], y=labels[::-1], orientation="h",
        marker_color=colors[::-1],
        text=[f"{v:.1f}%" for v in values[::-1]],
        textposition="outside", textfont=dict(color="#94a3b8", size=11),
    ))
    fig.update_layout(**themed(
        height=height,
        title="Key Demand Drivers (SHAP)",
        showlegend=False,
        xaxis_title="Relative Importance (%)",
    ))
    return fig


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"
