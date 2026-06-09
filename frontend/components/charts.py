"""
Reusable Plotly chart builders using the platform dark theme.
All update_layout calls use themed(**kwargs) to avoid duplicate-key errors.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any
import pandas as pd
import plotly.graph_objects as go

from frontend.components.theme import themed, C_INDIGO, C_EMERALD, C_AMBER, C_RED


def forecast_chart(historical: Dict, forecast: Dict,
                    historical_daily: Optional[Dict] = None,
                    forecast_daily: Optional[Dict] = None,
                    title: str = "Demand Forecast",
                    unit: str = "Units", height: int = 420) -> go.Figure:
    fig = go.Figure()

    hist_dates  = historical.get("dates", [])
    hist_values = historical.get("values", [])
    fc_dates    = forecast.get("dates", [])
    fc_values   = forecast.get("values", [])
    fc_lower    = forecast.get("lower", fc_values)
    fc_upper    = forecast.get("upper", fc_values)

    has_daily = bool(historical_daily and historical_daily.get("dates"))

    # ── Helper: convert monthly total → daily average ─────────────────
    def _to_daily_avg(dates: list, values: list) -> list:
        out = []
        for d_str, v in zip(dates, values):
            try:
                ts   = pd.Timestamp(d_str)
                days = (ts + pd.offsets.MonthEnd(1)).day
                out.append(round(v / days, 2))
            except Exception:
                out.append(v)
        return out

    # ── Separator + annotation helper ─────────────────────────────────
    def _add_separator(x0: str):
        fig.add_shape(
            type="line", x0=x0, x1=x0, y0=0, y1=1, yref="paper",
            line=dict(color="rgba(148,163,184,0.45)", width=1.5, dash="dot"),
        )
        fig.add_annotation(
            x=x0, y=0.97, yref="paper", text="  Forecast →",
            showarrow=False,
            font=dict(color="#94a3b8", size=11, family="Inter, sans-serif"),
            bgcolor="rgba(17,17,40,0.75)",
            bordercolor="rgba(99,102,241,0.4)",
            borderwidth=1, borderpad=4, xanchor="left", yanchor="top",
        )

    # ── DAILY MODE ────────────────────────────────────────────────────
    if has_daily:
        d_dates  = historical_daily.get("dates", [])
        d_values = historical_daily.get("values", [])
        fd_dates  = (forecast_daily or {}).get("dates",  [])
        fd_values = (forecast_daily or {}).get("values", [])
        fd_lower  = (forecast_daily or {}).get("lower",  [])
        fd_upper  = (forecast_daily or {}).get("upper",  [])

        # Monthly data expressed as daily averages (same y-scale as daily bars)
        hist_avg = _to_daily_avg(hist_dates, hist_values)
        fc_avg   = _to_daily_avg(fc_dates,   fc_values)
        fc_lo_avg = _to_daily_avg(fc_dates, fc_lower)
        fc_hi_avg = _to_daily_avg(fc_dates, fc_upper)

        # 1. 90% CI band (daily scale) — commented out for now
        # if fd_dates and fd_upper and fd_lower:
        #     fig.add_trace(go.Scatter(
        #         x=fd_dates + fd_dates[::-1],
        #         y=fd_upper + fd_lower[::-1],
        #         fill="toself",
        #         fillcolor="rgba(16,185,129,0.10)",
        #         line=dict(color="rgba(16,185,129,0.28)", width=0.8),
        #         showlegend=True, name="90% CI",
        #         hoverinfo="skip",
        #     ))

        # 2. Daily historical bars — raw market texture
        fig.add_trace(go.Bar(
            x=d_dates, y=d_values,
            name="Daily (actual)",
            marker=dict(color="rgba(99,102,241,0.35)", line=dict(width=0)),
            hovertemplate="<b>%{y:,.0f}</b><extra>Daily actual</extra>",
        ))

        # 3. Monthly historical → daily average trend line
        if hist_dates and hist_avg:
            fig.add_trace(go.Scatter(
                x=hist_dates, y=hist_avg,
                name="Monthly avg / day",
                line=dict(color="#818cf8", width=2.5),
                mode="lines+markers",
                marker=dict(size=5, color="#818cf8", line=dict(color="#4f46e5", width=1)),
                hovertemplate="<b>%{y:,.1f} / day</b><extra>Monthly avg</extra>",
            ))

        # 4. Daily forecast bars (flat step per month)
        if fd_dates and fd_values:
            fig.add_trace(go.Bar(
                x=fd_dates, y=fd_values,
                name="Forecast (daily avg)",
                marker=dict(color="rgba(16,185,129,0.35)", line=dict(width=0)),
                hovertemplate="<b>%{y:,.1f} / day</b><extra>Forecast</extra>",
            ))

        # 5. Monthly forecast → daily average dashed trend line
        if fc_dates and fc_avg:
            fig.add_trace(go.Scatter(
                x=fc_dates, y=fc_avg,
                name="Forecast trend",
                line=dict(color="#34d399", width=2.5, dash="dash"),
                mode="lines+markers",
                marker=dict(size=5, color="#34d399", line=dict(color="#059669", width=1)),
                hovertemplate="<b>%{y:,.1f} / day</b><extra>Forecast trend</extra>",
            ))

        # Handoff dot
        if hist_avg and fc_dates:
            fig.add_trace(go.Scatter(
                x=[fc_dates[0]], y=[hist_avg[-1]],
                mode="markers",
                marker=dict(color="#f1f5f9", size=9, line=dict(color="#6366f1", width=2.5)),
                showlegend=False, hoverinfo="skip",
            ))

        if fc_dates:
            _add_separator(fc_dates[0])

        y_unit = unit.replace("/ Month", "/ Day").replace("/Month", "/Day")

    # ── MONTHLY MODE (fallback) ───────────────────────────────────────
    else:
        if hist_dates and hist_values:
            fig.add_trace(go.Scatter(
                x=hist_dates, y=hist_values,
                fill="tozeroy", fillcolor="rgba(99,102,241,0.12)",
                line=dict(color="rgba(0,0,0,0)", width=0),
                showlegend=False, hoverinfo="skip",
            ))
        if hist_dates and hist_values:
            fig.add_trace(go.Scatter(
                x=hist_dates, y=hist_values,
                name="Historical",
                line=dict(color="#818cf8", width=2.5),
                mode="lines",
                hovertemplate="<b>%{y:,.0f}</b><extra>Historical</extra>",
            ))
        if fc_dates and fc_values:
            # 90% CI band — commented out for now
            # fig.add_trace(go.Scatter(
            #     x=fc_dates + fc_dates[::-1], y=fc_upper + fc_lower[::-1],
            #     fill="toself", fillcolor="rgba(16,185,129,0.13)",
            #     line=dict(color="rgba(16,185,129,0.35)", width=1),
            #     showlegend=True, name="90% CI", hoverinfo="skip",
            # ))
            fig.add_trace(go.Scatter(
                x=fc_dates, y=fc_values,
                fill="tozeroy", fillcolor="rgba(16,185,129,0.05)",
                line=dict(color="rgba(0,0,0,0)", width=0),
                showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=fc_dates, y=fc_values,
                name="Forecast",
                line=dict(color="#34d399", width=2.5, dash="dash"),
                mode="lines",
                hovertemplate="<b>%{y:,.0f}</b><extra>Forecast</extra>",
            ))
            if hist_values:
                fig.add_trace(go.Scatter(
                    x=[fc_dates[0]], y=[hist_values[-1]], mode="markers",
                    marker=dict(color="#f1f5f9", size=8,
                                line=dict(color="#6366f1", width=2.5)),
                    showlegend=False, hoverinfo="skip",
                ))
            _add_separator(fc_dates[0])
        y_unit = unit

    # ── Shared layout ─────────────────────────────────────────────────
    fig.update_layout(**themed(
        height=height,
        title=title,
        yaxis_title=y_unit,
        xaxis_title="",
        hovermode="x unified",
        yaxis_tickformat=",",
        barmode="overlay",
        xaxis=dict(
            gridcolor="rgba(30,30,63,0.8)", gridwidth=1,
            linecolor="#1e1e3f", tickcolor="#1e1e3f",
            tickfont=dict(color="#64748b", size=11),
            zeroline=False,
            showspikes=True, spikecolor="rgba(99,102,241,0.5)",
            spikethickness=1, spikedash="dot", spikemode="across",
            rangeselector=dict(
                buttons=[
                    dict(count=3,  label="3M", step="month", stepmode="backward"),
                    dict(count=6,  label="6M", step="month", stepmode="backward"),
                    dict(count=1,  label="1Y", step="year",  stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="#111128", activecolor="#6366f1",
                bordercolor="#1e1e3f", borderwidth=1,
                font=dict(color="#94a3b8", size=11),
                x=0, y=1.0,
            ),
        ),
        yaxis=dict(
            gridcolor="rgba(30,30,63,0.6)", gridwidth=1,
            linecolor="#1e1e3f", tickcolor="#1e1e3f",
            tickfont=dict(color="#64748b", size=11),
            zeroline=True, zerolinecolor="rgba(30,30,63,0.9)", zerolinewidth=1,
            showspikes=True, spikecolor="rgba(99,102,241,0.4)",
            spikethickness=1, spikedash="dot", spikemode="across",
            title_font=dict(color="#94a3b8", size=12),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(13,13,32,0.85)", bordercolor="rgba(30,30,63,0.9)",
            borderwidth=1, font=dict(color="#94a3b8", size=12),
        ),
        hoverlabel=dict(
            bgcolor="#111128", bordercolor="#6366f1",
            font=dict(color="#f1f5f9", size=12, family="Inter, sans-serif"),
            namelength=-1,
        ),
        margin=dict(l=64, r=24, t=72, b=44),
        plot_bgcolor="rgba(7,7,26,0.4)",
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
                   title: str = "", height: int = 420,
                   xaxis_title: str = "", yaxis_title: str = "") -> go.Figure:
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
    fig.update_layout(**themed(
        height=height, title=title,
        xaxis_title=xaxis_title or x.replace("_", " ").title(),
        yaxis_title=yaxis_title or y.replace("_", " ").title(),
    ))
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
    labels   = [f.get("label", f.get("feature", "")) for f in features]
    values   = [f.get("importance_pct", f.get("importance", 0)) for f in features]
    colors   = [C_EMERALD if f.get("direction") == "positive" else C_INDIGO for f in features]
    descs    = [f.get("description", "") for f in features]

    fig = go.Figure(go.Bar(
        x=values[::-1], y=labels[::-1], orientation="h",
        marker=dict(
            color=colors[::-1],
            line=dict(color="rgba(0,0,0,0)", width=0),
        ),
        text=[f"{v:.1f}%" for v in values[::-1]],
        textposition="outside",
        textfont=dict(color="#94a3b8", size=11),
        customdata=descs[::-1],
        hovertemplate=(
            "<b style='color:#f1f5f9'>%{y}</b><br>"
            "<span style='color:#94a3b8'>%{customdata}</span><br><br>"
            "Importance: <b>%{x:.1f}%</b>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(**themed(
        height=height,
        title="Key Demand Drivers (SHAP)",
        showlegend=False,
        xaxis_title="Relative Importance (%)",
        hoverlabel=dict(
            bgcolor="#111128",
            bordercolor="#6366f1",
            font=dict(color="#f1f5f9", size=12, family="Inter, sans-serif"),
            namelength=-1,
        ),
    ))
    return fig


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"
