import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.connection import get_db_session
from database.queries import (
    get_yoy_comparison, get_sales_by_category, get_sales_by_region,
    get_chinese_brand_yearly_share, get_price_competitiveness,
    get_ev_segment_by_brand_year, get_market_share_shift,
    CHINESE_BRANDS, BRAND_ORIGIN,
)
from utils.helpers import get_color_palette, render_kpi_card

_CHINESE_COLORS = {
    'MG':     '#ef4444',
    'BYD':    '#f97316',
    'Jetour': '#eab308',
    'Geely':  '#84cc16',
}

_ORIGIN_COLORS = {
    'Chinese':  '#ef4444',
    'Japanese': '#3b82f6',
    'Korean':   '#8b5cf6',
    'European': '#f59e0b',
    'American': '#10b981',
    'Other':    '#6b7280',
}

_EV_COLORS = {
    'BYD':        '#ef4444',
    'Tesla':      '#10b981',
    'MG':         '#f97316',
    'Korean EVs': '#8b5cf6',
    'German EVs': '#f59e0b',
    'Others':     '#6b7280',
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
                format_func=lambda x: "Revenue (AED)" if x == "revenue" else "Sales Volume (Units)",
                horizontal=True,
            )

            fig_yoy = px.line(
                df_yoy, x='month_name', y=target_metric, color='year',
                markers=True,
                category_orders={'month_name': months_order},
                color_discrete_sequence=colors['colors_seq'],
                labels={'month_name': 'Month', 'revenue': 'Revenue (AED)',
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
                    reg_df, x='emirate', y='revenue',
                    color='emirate', color_discrete_sequence=colors['colors_seq'],
                )
                fig_reg.update_layout(
                    **{**_BASE_LAYOUT, 'height': 300, 'showlegend': False,
                       'xaxis': dict(showgrid=False, title=""),
                       'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Revenue (AED)")}
                )
                st.plotly_chart(fig_reg, use_container_width=True)
            else:
                st.info("No regional data.")

        # ═══════════════════════════════════════════════════════════════════════
        # CHINESE BRAND MARKET IMPACT
        # ═══════════════════════════════════════════════════════════════════════
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
            <div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:24px; margin-bottom:4px;">
                <h2 style="background:linear-gradient(135deg,#ef4444 0%,#f97316 50%,#eab308 100%);
                           -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                           font-weight:800; margin-bottom:4px;">
                    Chinese Brand Pressure on UAE Market
                </h2>
                <p style="color:#9ca3af; font-size:13px; margin-top:0;">
                    MG &middot; BYD &middot; Jetour &middot; Geely &nbsp;&mdash;&nbsp;
                    market entry, price disruption &amp; EV takeover &nbsp;|&nbsp;
                    Source: BestSellingCarsBlog &middot; Focus2move &middot; DubiCars H1 2025
                </p>
            </div>
        """, unsafe_allow_html=True)

        # All China-section queries ignore the brand sidebar filter
        china_f   = {**filters, 'brand': None}
        df_yearly = get_chinese_brand_yearly_share(session, china_f)
        df_price  = get_price_competitiveness(session, china_f)
        df_ev     = get_ev_segment_by_brand_year(session, china_f)
        df_shift  = get_market_share_shift(session, filters)

        if df_yearly.empty:
            st.info("No sales data available for the selected filters.")
        else:
            # ── KPI preparation ──────────────────────────────────────────────
            year_totals    = df_yearly.groupby('year')['units'].sum()
            chinese_yearly = (
                df_yearly[df_yearly['brand'].isin(CHINESE_BRANDS)]
                .groupby('year')['units'].sum()
            )
            share_by_year = (chinese_yearly / year_totals * 100).round(1)

            latest_year   = int(df_yearly['year'].max())
            earliest_year = int(df_yearly['year'].min())
            latest_share  = float(share_by_year.get(latest_year, 0.0))
            base_share    = float(share_by_year.get(earliest_year, 0.0))
            share_delta   = round(latest_share - base_share, 1)

            # BYD EV segment share in latest EV year
            byd_ev_share = 0.0
            if not df_ev.empty:
                ev_latest    = df_ev[df_ev['year'] == df_ev['year'].max()]
                ev_total     = ev_latest['ev_units'].sum()
                byd_units    = ev_latest[ev_latest['brand'] == 'BYD']['ev_units'].sum()
                byd_ev_share = round(float(byd_units / ev_total * 100), 1) if ev_total else 0.0

            # Price gap: Chinese SUV weighted avg vs rest of market SUV weighted avg
            price_gap_aed = 0
            if not df_price.empty:
                suv_df  = df_price[df_price['vehicle_category'] == 'SUV'].copy()
                cn_suv  = suv_df[suv_df['origin'] == 'Chinese']
                oth_suv = suv_df[suv_df['origin'] != 'Chinese']
                if not cn_suv.empty and not oth_suv.empty:
                    price_gap_aed = int(_wt_avg_price(oth_suv) - _wt_avg_price(cn_suv))

            # Projected 2027 share — use only 2022+ where Chinese brands had real presence
            proj_2027 = None
            recent = share_by_year[share_by_year.index >= 2022]
            if len(recent) >= 3:
                yrs   = np.array(recent.index, dtype=float)
                shrs  = np.array(recent.values, dtype=float)
                coeff = np.polyfit(yrs, shrs, 1)
                proj_2027 = round(min(float(np.polyval(coeff, 2027)), 55.0), 1)

            # ── KPI Cards ────────────────────────────────────────────────────
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                year_label = f"{latest_year} (Jan–May)" if latest_year == 2026 else str(latest_year)
                render_kpi_card(
                    f"Chinese Brand Share ({year_label})",
                    f"{latest_share:.1f}%",
                    f"+{share_delta}pp since {earliest_year}",
                    is_positive=True,
                )
            with k2:
                render_kpi_card(
                    f"BYD EV Segment Share ({latest_year})",
                    f"{byd_ev_share:.1f}%",
                    "of total UAE EV market",
                    is_positive=True,
                )
            with k3:
                render_kpi_card(
                    "Chinese SUV Price Advantage",
                    f"AED {price_gap_aed:,}",
                    "cheaper vs rest of market",
                    is_positive=True,
                )
            with k4:
                if proj_2027 is not None:
                    render_kpi_card(
                        "Projected 2027 Share",
                        f"{proj_2027:.1f}%",
                        "based on 2022-2026 trend",
                        is_positive=True,
                    )
                else:
                    render_kpi_card("Projected 2027 Share", "N/A", "insufficient data", is_positive=False)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Row 1: Market Share Growth  +  Volume Comparison ─────────────
            r1c1, r1c2 = st.columns(2)

            with r1c1:
                st.markdown("### Chinese Brand Market Share Growth")
                year_tot_df = year_totals.reset_index().rename(columns={'units': 'year_total'})
                cn_area     = df_yearly[df_yearly['brand'].isin(CHINESE_BRANDS)].copy()
                cn_area     = cn_area.merge(year_tot_df, on='year')
                cn_area['share_pct'] = (cn_area['units'] / cn_area['year_total'] * 100).round(2)

                # Fill zeros for years where a brand had no sales yet
                all_years = sorted(df_yearly['year'].unique())
                full_idx  = pd.MultiIndex.from_product(
                    [all_years, CHINESE_BRANDS], names=['year', 'brand']
                )
                cn_area = (
                    cn_area.set_index(['year', 'brand'])[['share_pct']]
                    .reindex(full_idx, fill_value=0.0)
                    .reset_index()
                )

                fig_area = px.area(
                    cn_area, x='year', y='share_pct', color='brand',
                    color_discrete_map=_CHINESE_COLORS,
                    labels={
                        'share_pct': '% of Total UAE Market',
                        'year': 'Year',
                        'brand': 'Brand',
                    },
                )
                fig_area.update_traces(line=dict(width=0.8))
                fig_area.update_layout(
                    **{**_BASE_LAYOUT, 'height': 320, 'hovermode': 'x unified',
                       'xaxis': dict(showgrid=False, dtick=1),
                       'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                     title='% of Total UAE Market')}
                )
                st.plotly_chart(fig_area, use_container_width=True)
                st.caption(
                    "Source: BestSellingCarsBlog UAE 2019–2025 · Focus2move Q1 2026 · "
                    "sample scaled ×17 to national volume"
                )

            with r1c2:
                st.markdown("### Chinese Brands vs Total Market Volume")
                cn_vol  = (
                    df_yearly[df_yearly['brand'].isin(CHINESE_BRANDS)]
                    .groupby('year')['units'].sum()
                    .reset_index().rename(columns={'units': 'chinese_units'})
                )
                tot_vol = year_totals.reset_index().rename(columns={'units': 'total_units'})
                vol_df  = tot_vol.merge(cn_vol, on='year', how='left').fillna(0)

                fig_vol = go.Figure()
                fig_vol.add_trace(go.Scatter(
                    x=vol_df['year'], y=vol_df['chinese_units'].astype(int),
                    name='Chinese Brands', mode='lines+markers',
                    line=dict(color='#ef4444', width=2.5),
                    marker=dict(size=7),
                    yaxis='y1',
                ))
                fig_vol.add_trace(go.Scatter(
                    x=vol_df['year'], y=vol_df['total_units'].astype(int),
                    name='Total UAE Market', mode='lines+markers',
                    line=dict(color='#6366f1', width=2.5, dash='dash'),
                    marker=dict(size=7),
                    yaxis='y2',
                ))
                fig_vol.update_layout(
                    **{**_BASE_LAYOUT, 'height': 320, 'hovermode': 'x unified',
                       'xaxis': dict(showgrid=False, dtick=1),
                       'yaxis':  dict(title='Chinese Brand Units', side='left',
                                      showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                       'yaxis2': dict(title='Total Market Units', side='right',
                                      overlaying='y', showgrid=False)}
                )
                st.plotly_chart(fig_vol, use_container_width=True)
                st.caption(
                    "Dual axis: left = Chinese brands, right = total UAE market. "
                    "Both scaled to national implied volume (sample ×17)."
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
                            'avg_price':    'Avg Selling Price (AED)',
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
                                         tickformat=',.0f', title='Avg Selling Price (AED)'),
                           'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                         tickformat=',.0f', title='Total Units Sold')}
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    st.caption(
                        "Bubble size = market share %. "
                        "Chinese brands (red) cluster bottom-left — high volume at low price."
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
                        cn_cat  = cat_df[cat_df['origin'] == 'Chinese']
                        oth_cat = cat_df[cat_df['origin'] != 'Chinese']
                        if cn_cat.empty or oth_cat.empty:
                            continue
                        cn_avg  = (cn_cat['price_x_units'].sum()  / cn_cat['units'].sum())
                        oth_avg = (oth_cat['price_x_units'].sum() / oth_cat['units'].sum())
                        gap_records += [
                            {'Category': cat, 'Group': 'Chinese Brands',  'Avg Price (AED)': round(cn_avg)},
                            {'Category': cat, 'Group': 'Rest of Market',  'Avg Price (AED)': round(oth_avg)},
                        ]

                    if gap_records:
                        gap_df  = pd.DataFrame(gap_records)
                        fig_gap = px.bar(
                            gap_df, x='Category', y='Avg Price (AED)',
                            color='Group', barmode='group',
                            color_discrete_map={
                                'Chinese Brands': '#ef4444',
                                'Rest of Market': '#6366f1',
                            },
                            text_auto=True,
                        )
                        fig_gap.update_traces(
                            texttemplate='AED %{y:,.0f}',
                            textposition='outside',
                            textfont_size=10,
                        )
                        fig_gap.update_layout(
                            **{**_BASE_LAYOUT, 'height': 360,
                               'xaxis': dict(showgrid=False),
                               'yaxis': dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                                             tickformat=',.0f', title='Weighted Avg Selling Price (AED)')}
                        )
                        st.plotly_chart(fig_gap, use_container_width=True)
                        st.caption(
                            "Weighted by units sold. "
                            "EV gap is BYD vs Tesla/German EVs. SUV gap driven by MG ZS vs Toyota RAV4/Fortuner."
                        )
                    else:
                        st.info("Insufficient category data for price gap analysis.")
                else:
                    st.info("No price data available.")

            # ── Row 3: EV Segment Ownership  +  Market Share Shift ───────────
            r3c1, r3c2 = st.columns(2)

            with r3c1:
                st.markdown("### EV Segment Ownership by Year")
                if not df_ev.empty:
                    def _classify_ev(brand: str) -> str:
                        if brand == 'BYD':                              return 'BYD'
                        if brand == 'Tesla':                            return 'Tesla'
                        if brand == 'MG':                               return 'MG'
                        if brand in ('Hyundai', 'Kia'):                 return 'Korean EVs'
                        if brand in ('BMW', 'Mercedes-Benz', 'Volkswagen'): return 'German EVs'
                        return 'Others'

                    ev_plot = df_ev.copy()
                    ev_plot['brand_group'] = ev_plot['brand'].apply(_classify_ev)
                    ev_agg = (
                        ev_plot.groupby(['year', 'brand_group'])['ev_units']
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

                    group_order = ['BYD', 'Tesla', 'MG', 'Korean EVs', 'German EVs', 'Others']
                    ev_agg['brand_group'] = pd.Categorical(
                        ev_agg['brand_group'], categories=group_order, ordered=True
                    )
                    ev_agg = ev_agg.sort_values(['year', 'brand_group'])

                    fig_ev = px.bar(
                        ev_agg, x='year', y='ev_share_pct', color='brand_group',
                        color_discrete_map=_EV_COLORS,
                        category_orders={'brand_group': group_order},
                        labels={
                            'ev_share_pct': '% of EV Segment',
                            'year': 'Year',
                            'brand_group': '',
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
                        "BYD overtook Tesla as UAE #1 EV brand in 2025. "
                        "MG4 adds a second Chinese EV pillar alongside BYD."
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
                    shift_plot['label'] = shift_plot.apply(
                        lambda r: f"{r['brand']} ★" if r['origin'] == 'Chinese' else r['brand'],
                        axis=1,
                    )
                    shift_plot['bar_color'] = shift_plot.apply(
                        lambda r: (
                            '#ef4444' if r['origin'] == 'Chinese' and r['share_change'] > 0
                            else '#fca5a5' if r['origin'] == 'Chinese'
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
                        "★ = Chinese brand. Red = Chinese gainer. Grey = non-Chinese loser. "
                        "Toyota and Nissan absorb the most share loss to Chinese entrants."
                    )
                else:
                    st.info("Insufficient data for market share shift analysis.")

    except Exception as e:
        st.error(f"Error rendering Comparative Analytics: {e}")
    finally:
        session.close()
