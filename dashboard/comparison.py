import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.connection import get_db_session
from database.queries import (
    get_yoy_comparison, get_sales_by_category, get_sales_by_region,
    get_brand_origin_yearly_share, get_price_competitiveness,
    get_ev_segment_by_brand_year, get_market_share_shift,
    IMPORT_BRANDS, BRAND_ORIGIN,
)
from utils.helpers import get_color_palette, render_kpi_card

_ORIGIN_COLORS = {
    'Domestic': '#10b981',
    'Japanese': '#3b82f6',
    'Korean':   '#8b5cf6',
    'European': '#f59e0b',
    'Other':    '#6b7280',
}

_BASE_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
    margin=dict(l=0, r=0, t=30, b=0),
    legend=dict(
        orientation='h', yanchor='bottom', y=1.02,
        xanchor='right', x=1, font=dict(size=11)
    ),
)


def _wt_avg_price(df: pd.DataFrame) -> float:
    total = df['units'].sum()
    return float((df['avg_price'] * df['units']).sum() / total) if total else 0.0


def _sequential_shades(n: int, base_hex: str) -> list:
    """n hex shades of base_hex running light -> dark, for ordered categories
    (e.g. oldest -> newest year) where color should read as one hue's intensity."""
    base = tuple(int(base_hex[i:i + 2], 16) for i in (1, 3, 5))
    light = tuple(int(c + (255 - c) * 0.75) for c in base)
    dark = tuple(int(c * 0.45) for c in base)
    shades = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 1.0
        rgb = tuple(int(light[j] + (dark[j] - light[j]) * t) for j in range(3))
        shades.append('#{:02x}{:02x}{:02x}'.format(*rgb))
    return shades


def render_comparison(filters: dict):
    session = get_db_session()
    colors  = get_color_palette()

    try:
        st.markdown(
            "<h2 class='gradient-text' style='margin-bottom: 20px;'>Comparative Analytics Dashboard</h2>",
            unsafe_allow_html=True,
        )

        # ── 1. YoY Overlap ──────────────────────────────────────────────────
        df_yoy = get_yoy_comparison(session, filters)

        if not df_yoy.empty:
            st.markdown("### Year-over-Year (YoY) Overlap Analysis")

            months_map = {
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',  5: 'May',  6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
            }
            df_yoy['month_name'] = df_yoy['month'].map(months_map)
            df_yoy['year']       = df_yoy['year'].astype(str)
            months_order         = list(months_map.values())

            target_metric = st.radio(
                "Compare Metric",
                options=["revenue", "sales"],
                format_func=lambda x: "Revenue (USD)" if x == "revenue" else "Sales Volume (Units)",
                horizontal=True,
            )

            years_sorted = sorted(df_yoy['year'].unique())
            year_shades = dict(zip(
                years_sorted, _sequential_shades(len(years_sorted), colors['primary'])
            ))

            fig_yoy = px.line(
                df_yoy, x='month_name', y=target_metric, color='year',
                markers=True,
                category_orders={'month_name': months_order, 'year': years_sorted},
                color_discrete_map=year_shades,
                labels={'month_name': 'Month', 'revenue': 'Revenue (USD)',
                        'sales': 'Sales Volume', 'year': 'Year'},
            )
            fig_yoy.update_layout(
                **{**_BASE_LAYOUT, 'height': 350,
                   'xaxis': dict(showgrid=False),
                   'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)')}
            )
            st.plotly_chart(fig_yoy, use_container_width=True)

            recent_years = df_yoy['year'].unique()
            if len(recent_years) >= 2:
                top_years = sorted(list(recent_years), reverse=True)[:2]
                y1 = df_yoy[df_yoy['year'] == top_years[0]][target_metric].sum()
                y2 = df_yoy[df_yoy['year'] == top_years[1]][target_metric].sum()
                if y2 > 0:
                    pct = ((y1 - y2) / y2) * 100
                    label = target_metric.replace('_', ' ').title()
                    st.info(
                        f"**YoY Performance Summary:** Total {label} in **{top_years[0]}** "
                        f"vs **{top_years[1]}** is **{pct:+.2f}%**."
                    )
        else:
            st.warning("Insufficient time-series data for Year-over-Year comparison.")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 2. Category + Region ─────────────────────────────────────────────
        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown("### Vehicle Category Growth Comparison")
            cat_df = get_sales_by_category(session, filters)
            if not cat_df.empty:
                fig_cat = px.bar(
                    cat_df, y='vehicle_category', x='sales', orientation='h',
                    color='vehicle_category', color_discrete_sequence=colors['colors_seq'],
                )
                fig_cat.update_layout(
                    **{**_BASE_LAYOUT, 'height': 300, 'showlegend': False,
                       'xaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Units Sold"),
                       'yaxis': dict(showgrid=False, title="", categoryorder='total ascending')}
                )
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.info("No category data.")

        with right_col:
            st.markdown("### Regional Growth Matrix")
            reg_df = get_sales_by_region(session, filters)
            if not reg_df.empty:
                fig_reg = px.bar(
                    reg_df, x='state', y='revenue',
                    color='state', color_discrete_sequence=colors['colors_seq'],
                )
                fig_reg.update_layout(
                    **{**_BASE_LAYOUT, 'height': 300, 'showlegend': False,
                       'xaxis': dict(showgrid=False, title=""),
                       'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Revenue (USD)")}
                )
                st.plotly_chart(fig_reg, use_container_width=True)
            else:
                st.info("No regional data.")

        # ═══════════════════════════════════════════════════════════════════════
        # IMPORT TARIFF EXPOSURE
        # ═══════════════════════════════════════════════════════════════════════
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
            <div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:24px; margin-bottom:4px;">
                <h2 style="background:linear-gradient(135deg,#ef4444 0%,#f97316 50%,#eab308 100%);
                           -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                           font-weight:800; margin-bottom:4px;">
                    Import Tariff Exposure
                </h2>
                <p style="color:#9ca3af; font-size:13px; margin-top:0;">
                    Domestic (Ford &middot; Chevrolet &middot; GMC &middot; Ram &middot; Jeep &middot; Tesla)
                    vs. Import (Japanese &middot; Korean &middot; European) brand share &nbsp;&mdash;&nbsp;
                    modeled against the 25% Section 232 auto tariff on imported vehicles that took effect in April 2025
                </p>
            </div>
        """, unsafe_allow_html=True)

        # All tariff-section queries ignore the brand sidebar filter
        origin_f  = {**filters, 'brand': None}
        df_yearly = get_brand_origin_yearly_share(session, origin_f)
        df_price  = get_price_competitiveness(session, origin_f)
        df_ev     = get_ev_segment_by_brand_year(session, origin_f)
        df_shift  = get_market_share_shift(session, filters)

        if df_yearly.empty:
            st.info("No sales data available for the selected filters.")
        else:
            # ── KPI preparation ──────────────────────────────────────────────
            year_totals   = df_yearly.groupby('year')['units'].sum()
            import_yearly = (
                df_yearly[df_yearly['brand'].isin(IMPORT_BRANDS)]
                .groupby('year')['units'].sum()
            )
            share_by_year = (import_yearly / year_totals * 100).round(1)

            latest_year   = int(df_yearly['year'].max())
            earliest_year = int(df_yearly['year'].min())
            latest_share  = float(share_by_year.get(latest_year, 0.0))
            base_share    = float(share_by_year.get(earliest_year, 0.0))
            share_delta   = round(latest_share - base_share, 1)

            # Domestic EV segment share in latest EV year
            domestic_ev_share = 0.0
            if not df_ev.empty:
                ev_latest = df_ev[df_ev['year'] == df_ev['year'].max()].copy()
                ev_latest['origin'] = ev_latest['brand'].map(BRAND_ORIGIN).fillna('Other')
                ev_total     = ev_latest['ev_units'].sum()
                dom_units    = ev_latest[ev_latest['origin'] == 'Domestic']['ev_units'].sum()
                domestic_ev_share = round(float(dom_units / ev_total * 100), 1) if ev_total else 0.0

            # Price gap: Import SUV weighted avg vs Domestic SUV weighted avg
            price_gap_usd = 0
            if not df_price.empty:
                suv_df  = df_price[df_price['vehicle_category'] == 'SUV'].copy()
                imp_suv = suv_df[suv_df['origin'].isin(['Japanese', 'Korean', 'European'])]
                dom_suv = suv_df[suv_df['origin'] == 'Domestic']
                if not imp_suv.empty and not dom_suv.empty:
                    price_gap_usd = int(_wt_avg_price(imp_suv) - _wt_avg_price(dom_suv))

            # Projected 2027 share — trend fit on the recent (2022+) window
            proj_2027 = None
            recent = share_by_year[share_by_year.index >= 2022]
            if len(recent) >= 3:
                yrs   = np.array(recent.index, dtype=float)
                shrs  = np.array(recent.values, dtype=float)
                coeff = np.polyfit(yrs, shrs, 1)
                proj_2027 = round(min(float(np.polyval(coeff, 2027)), 100.0), 1)

            # ── KPI Cards ────────────────────────────────────────────────────
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                year_label = f"{latest_year} (Jan–May)" if latest_year == 2026 else str(latest_year)
                render_kpi_card(
                    f"Import Brand Share ({year_label})",
                    f"{latest_share:.1f}%",
                    f"{share_delta:+}pp since {earliest_year}",
                    is_positive=(share_delta <= 0),
                )
            with k2:
                render_kpi_card(
                    f"Domestic EV Segment Share ({latest_year})",
                    f"{domestic_ev_share:.1f}%",
                    "of total US EV market",
                    is_positive=True,
                )
            with k3:
                render_kpi_card(
                    "Import SUV Price Premium",
                    f"${price_gap_usd:,}",
                    "import vs. domestic avg",
                    is_positive=(price_gap_usd <= 0),
                )
            with k4:
                if proj_2027 is not None:
                    render_kpi_card(
                        "Projected 2027 Import Share",
                        f"{proj_2027:.1f}%",
                        "based on 2022-2026 trend",
                        is_positive=False,
                    )
                else:
                    render_kpi_card("Projected 2027 Import Share", "N/A", "insufficient data", is_positive=False)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Row 1: Origin Share Growth  +  Volume Comparison ─────────────
            r1c1, r1c2 = st.columns(2)

            with r1c1:
                st.markdown("### Brand Origin Market Share Growth")
                year_tot_df = year_totals.reset_index().rename(columns={'units': 'year_total'})
                origin_area = df_yearly.groupby(['year', 'origin'])['units'].sum().reset_index()
                origin_area = origin_area.merge(year_tot_df, on='year')
                origin_area['share_pct'] = (origin_area['units'] / origin_area['year_total'] * 100).round(2)

                # Fill zeros for years where an origin had no sales yet
                all_years         = sorted(df_yearly['year'].unique())
                origin_categories = ['Domestic', 'Japanese', 'Korean', 'European', 'Other']
                full_idx = pd.MultiIndex.from_product(
                    [all_years, origin_categories], names=['year', 'origin']
                )
                origin_area = (
                    origin_area.set_index(['year', 'origin'])[['share_pct']]
                    .reindex(full_idx, fill_value=0.0)
                    .reset_index()
                )

                fig_area = px.area(
                    origin_area, x='year', y='share_pct', color='origin',
                    color_discrete_map=_ORIGIN_COLORS,
                    labels={
                        'share_pct': '% of Total US Market',
                        'year': 'Year',
                        'origin': 'Origin',
                    },
                )
                fig_area.update_traces(line=dict(width=0.8))
                fig_area.update_layout(
                    **{**_BASE_LAYOUT, 'height': 320, 'hovermode': 'x unified',
                       'xaxis': dict(showgrid=False, dtick=1),
                       'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                     title='% of Total US Market')}
                )
                st.plotly_chart(fig_area, use_container_width=True)
                st.caption(
                    "Sample scaled to national implied volume. "
                    "Import share reflects the combined Japanese, Korean and European brand groups."
                )

            with r1c2:
                st.markdown("### Import Brands vs Total Market Volume")
                imp_vol = (
                    df_yearly[df_yearly['brand'].isin(IMPORT_BRANDS)]
                    .groupby('year')['units'].sum()
                    .reset_index().rename(columns={'units': 'import_units'})
                )
                tot_vol = year_totals.reset_index().rename(columns={'units': 'total_units'})
                vol_df  = tot_vol.merge(imp_vol, on='year', how='left').fillna(0)

                fig_vol = go.Figure()
                fig_vol.add_trace(go.Scatter(
                    x=vol_df['year'], y=vol_df['import_units'].astype(int),
                    name='Import Brands', mode='lines+markers',
                    line=dict(color='#ef4444', width=2.5),
                    marker=dict(size=7),
                    yaxis='y1',
                ))
                fig_vol.add_trace(go.Scatter(
                    x=vol_df['year'], y=vol_df['total_units'].astype(int),
                    name='Total US Market', mode='lines+markers',
                    line=dict(color='#6366f1', width=2.5, dash='dash'),
                    marker=dict(size=7),
                    yaxis='y2',
                ))
                fig_vol.update_layout(
                    **{**_BASE_LAYOUT, 'height': 320, 'hovermode': 'x unified',
                       'xaxis': dict(showgrid=False, dtick=1),
                       'yaxis':  dict(title='Import Brand Units', side='left',
                                      showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                       'yaxis2': dict(title='Total Market Units', side='right',
                                      overlaying='y', showgrid=False)}
                )
                st.plotly_chart(fig_vol, use_container_width=True)
                st.caption(
                    "Dual axis: left = import brands, right = total US market. "
                    "Both scaled to national implied volume."
                )

            # ── Row 2: Price Competitiveness Matrix  +  Price Gap by Category ─
            r2c1, r2c2 = st.columns(2)

            with r2c1:
                st.markdown("### Price Competitiveness Matrix")
                if not df_price.empty:
                    # Weighted avg price per brand across all categories
                    df_price['price_x_units'] = df_price['avg_price'] * df_price['units']
                    brand_agg = (
                        df_price.groupby(['brand', 'origin'])
                        .agg(
                            price_x_units =('price_x_units', 'sum'),
                            total_units   =('units', 'sum'),
                            market_share  =('market_share_pct', 'sum'),
                        )
                        .reset_index()
                    )
                    brand_agg['avg_price'] = (
                        brand_agg['price_x_units'] / brand_agg['total_units']
                    ).round(0)
                    brand_agg = brand_agg.drop(columns=['price_x_units'])

                    fig_scatter = px.scatter(
                        brand_agg,
                        x='avg_price', y='total_units',
                        color='origin', size='market_share',
                        text='brand',
                        color_discrete_map=_ORIGIN_COLORS,
                        size_max=45,
                        labels={
                            'avg_price':    'Avg Selling Price (USD)',
                            'total_units':  'Total Units Sold',
                            'origin':       'Brand Origin',
                            'market_share': 'Market Share %',
                        },
                    )
                    fig_scatter.update_traces(
                        textposition='top center', textfont_size=9,
                    )
                    fig_scatter.update_layout(
                        **{**_BASE_LAYOUT, 'height': 360,
                           'xaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                         tickformat=',.0f', title='Avg Selling Price (USD)'),
                           'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                         tickformat=',.0f', title='Total Units Sold')}
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    st.caption(
                        "Bubble size = market share %. "
                        "Import-origin brands (Japanese/Korean/European) carry the Section 232 tariff's price pressure; "
                        "Domestic brands (green) are exempt."
                    )
                else:
                    st.info("No price data available.")

            with r2c2:
                st.markdown("### Price Gap by Vehicle Category")
                if not df_price.empty:
                    df_price['price_x_units'] = df_price['avg_price'] * df_price['units']
                    gap_records = []
                    for cat in ['SUV', 'EV', 'Sedan']:
                        cat_df  = df_price[df_price['vehicle_category'] == cat]
                        imp_cat = cat_df[cat_df['origin'].isin(['Japanese', 'Korean', 'European'])]
                        dom_cat = cat_df[cat_df['origin'] == 'Domestic']
                        if imp_cat.empty or dom_cat.empty:
                            continue
                        imp_avg = (imp_cat['price_x_units'].sum() / imp_cat['units'].sum())
                        dom_avg = (dom_cat['price_x_units'].sum() / dom_cat['units'].sum())
                        gap_records += [
                            {'Category': cat, 'Group': 'Import Brands',   'Avg Price (USD)': round(imp_avg)},
                            {'Category': cat, 'Group': 'Domestic Brands', 'Avg Price (USD)': round(dom_avg)},
                        ]

                    if gap_records:
                        gap_df  = pd.DataFrame(gap_records)
                        fig_gap = px.bar(
                            gap_df, x='Category', y='Avg Price (USD)',
                            color='Group', barmode='group',
                            color_discrete_map={
                                'Import Brands':   '#ef4444',
                                'Domestic Brands':  '#10b981',
                            },
                            text_auto=True,
                        )
                        fig_gap.update_traces(
                            texttemplate='$%{y:,.0f}',
                            textposition='outside',
                            textfont_size=10,
                        )
                        fig_gap.update_layout(
                            **{**_BASE_LAYOUT, 'height': 360,
                               'xaxis': dict(showgrid=False),
                               'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                             tickformat=',.0f', title='Weighted Avg Selling Price (USD)')}
                        )
                        st.plotly_chart(fig_gap, use_container_width=True)
                        st.caption(
                            "Weighted by units sold. "
                            "Import prices reflect the pass-through of the 25% Section 232 tariff on imported vehicles."
                        )
                    else:
                        st.info("Insufficient category data for price gap analysis.")
                else:
                    st.info("No price data available.")

            # ── Row 3: EV Segment Ownership  +  Market Share Shift ───────────
            r3c1, r3c2 = st.columns(2)

            with r3c1:
                st.markdown("### EV Segment Ownership by Origin")
                if not df_ev.empty:
                    ev_plot = df_ev.copy()
                    ev_plot['origin'] = ev_plot['brand'].map(BRAND_ORIGIN).fillna('Other')
                    ev_agg = (
                        ev_plot.groupby(['year', 'origin'])['ev_units']
                        .sum().reset_index()
                    )
                    ev_yr_tot = (
                        ev_agg.groupby('year')['ev_units'].sum()
                        .reset_index().rename(columns={'ev_units': 'ev_total'})
                    )
                    ev_agg = ev_agg.merge(ev_yr_tot, on='year')
                    ev_agg['ev_share_pct'] = (
                        ev_agg['ev_units'] / ev_agg['ev_total'] * 100
                    ).round(1)

                    group_order = ['Domestic', 'Japanese', 'Korean', 'European', 'Other']
                    ev_agg['origin'] = pd.Categorical(
                        ev_agg['origin'], categories=group_order, ordered=True
                    )
                    ev_agg = ev_agg.sort_values(['year', 'origin'])

                    fig_ev = px.bar(
                        ev_agg, x='year', y='ev_share_pct', color='origin',
                        color_discrete_map=_ORIGIN_COLORS,
                        category_orders={'origin': group_order},
                        labels={
                            'ev_share_pct': '% of EV Segment',
                            'year': 'Year',
                            'origin': '',
                        },
                    )
                    fig_ev.update_layout(
                        **{**_BASE_LAYOUT, 'barmode': 'stack', 'height': 360,
                           'xaxis': dict(showgrid=False, dtick=1, type='category'),
                           'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                         title='% of EV Segment')}
                    )
                    st.plotly_chart(fig_ev, use_container_width=True)
                    st.caption(
                        "Domestic EV volume is anchored by Tesla; import-origin EV share reflects "
                        "Japanese, Korean and European entrants competing for the remaining segment."
                    )
                else:
                    st.info("No EV segment data available.")

            with r3c2:
                st.markdown("### Market Share Shift")
                if not df_shift.empty:
                    base_yr = int(df_shift['base_year'].iloc[0])
                    curr_yr = int(df_shift['curr_year'].iloc[0])
                    st.markdown(
                        f"<p style='color:#9ca3af; font-size:13px; margin-top:-12px;'>"
                        f"{base_yr} → {curr_yr} &mdash; who gained, who lost</p>",
                        unsafe_allow_html=True,
                    )

                    shift_plot = df_shift.sort_values('share_change', ascending=True).copy()
                    shift_plot['is_import'] = shift_plot['origin'] != 'Domestic'
                    shift_plot['label'] = shift_plot.apply(
                        lambda r: f"{r['brand']} ★" if r['is_import'] else r['brand'],
                        axis=1,
                    )
                    shift_plot['bar_color'] = shift_plot.apply(
                        lambda r: (
                            '#ef4444' if r['is_import'] and r['share_change'] < 0
                            else '#fca5a5' if r['is_import']
                            else '#10b981' if r['share_change'] > 0
                            else '#4b5563'
                        ),
                        axis=1,
                    )

                    fig_shift = go.Figure(go.Bar(
                        x=shift_plot['share_change'],
                        y=shift_plot['label'],
                        orientation='h',
                        marker_color=shift_plot['bar_color'].tolist(),
                        text=shift_plot['share_change'].apply(lambda x: f"{x:+.1f}pp"),
                        textposition='outside',
                        textfont=dict(size=10, color='#f3f4f6'),
                    ))
                    fig_shift.add_vline(
                        x=0, line_color='rgba(255,255,255,0.25)', line_width=1.5
                    )
                    fig_shift.update_layout(
                        **{**_BASE_LAYOUT, 'height': 420,
                           'margin': dict(l=90, r=70, t=10, b=30),
                           'xaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                         title='Market Share Change (percentage points)', zeroline=False),
                           'yaxis': dict(showgrid=False, title=''),
                           'legend': dict(visible=False)}
                    )
                    st.plotly_chart(fig_shift, use_container_width=True)
                    st.caption(
                        "★ = Import-origin brand. Red = import brand losing share, consistent with cost pressure "
                        "from the Section 232 tariff. Grey = domestic brand losing share."
                    )
                else:
                    st.info("Insufficient data for market share shift analysis.")

    except Exception as e:
        st.error(f"Error rendering Comparative Analytics: {e}")
    finally:
        session.close()
