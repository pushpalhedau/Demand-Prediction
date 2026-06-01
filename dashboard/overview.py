import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session
from database.queries import (
    get_executive_kpis, get_monthly_revenue_trend, get_sales_by_category, get_sales_by_fuel_type, get_sales_by_region,
    get_registration_kpis, get_monthly_registration_trend, get_registrations_by_maker,
    get_registrations_by_fuel, get_registrations_by_vehicle_class,
)
from utils.helpers import render_kpi_card, get_color_palette

def render_overview(filters: dict):
    """
    Renders the Executive Overview tab.
    """
    session = get_db_session()
    colors = get_color_palette()
    
    try:
        # Try India registration KPIs first; fall back to UAE KPIs
        india_kpis = get_registration_kpis(session, filters)
        use_india = india_kpis.get("total_registrations", 0) > 0

        st.markdown("<h2 class='gradient-text' style='margin-bottom: 25px;'>Executive Business Overview</h2>", unsafe_allow_html=True)

        if use_india:
            # ── India / VAHAN KPI cards ────────────────────────────────────
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                yoy = india_kpis.get("yoy_growth_pct")
                yoy_str = f"{yoy:+.1f}% YoY" if yoy is not None else "N/A"
                render_kpi_card("Total Registrations", f"{india_kpis['total_registrations']:,}", delta=yoy_str, is_positive=(yoy or 0) >= 0)
            with col2:
                render_kpi_card("EV Share", f"{india_kpis['ev_share_pct']:.2f}%",
                                delta=f"{india_kpis['total_ev_registrations']:,} EVs",
                                is_positive=india_kpis['ev_share_pct'] > 2)
            with col3:
                yoy = india_kpis.get("yoy_growth_pct")
                render_kpi_card("YoY Growth", f"{yoy:+.1f}%" if yoy is not None else "N/A",
                                delta="vs prior year period", is_positive=(yoy or 0) >= 0)
            with col4:
                render_kpi_card("Top Maker", india_kpis.get("top_maker", "N/A"),
                                delta=f"Lowest: {india_kpis.get('worst_state', 'N/A')}", is_positive=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Monthly Registration Trend ─────────────────────────────────
            st.markdown("### Monthly Registration Trend")
            trend_df = get_monthly_registration_trend(session, filters)
        else:
            # ── UAE legacy KPI cards (fallback) ───────────────────────────
            kpis = get_executive_kpis(session, filters)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                sales_delta_str = f"{kpis['total_sales_delta']:.2f}% YoY" if kpis['total_sales_delta'] is not None else "N/A"
                render_kpi_card("Total Sales Volume", f"{kpis['total_sales']:,} units", delta=sales_delta_str, is_positive=(kpis['total_sales_delta'] or 0) >= 0)
            with col2:
                rev_delta = f"{kpis['total_revenue_delta']:.2f}% YoY" if kpis['total_revenue_delta'] is not None else "N/A"
                render_kpi_card("Total Revenue", f"AED {kpis['total_revenue'] / 1_000_000:.2f}M", delta=rev_delta, is_positive=(kpis['total_revenue_delta'] or 0) >= 0)
            with col3:
                disc_delta = f"{kpis['avg_discount_delta']:+.2f}pp" if kpis['avg_discount_delta'] is not None else "N/A"
                render_kpi_card("Average Discount", f"{kpis['avg_discount']:.2f}%", delta=disc_delta, is_positive=(kpis['avg_discount_delta'] or 0) < 0)
            with col4:
                lc_delta = f"{abs(kpis['avg_lead_close_delta'] or 0):.0f} days faster" if (kpis['avg_lead_close_delta'] or 0) > 0 else "N/A"
                render_kpi_card("Avg Closing Velocity", f"{kpis['avg_lead_close']:.1f} Days", delta=lc_delta, is_positive=(kpis['avg_lead_close_delta'] or 0) >= 0)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### Revenue & Sales Growth Trend")
            trend_df = get_monthly_revenue_trend(session, filters)
        
        if not trend_df.empty:
            fig = go.Figure()
            if use_india:
                y_col, y_label = 'registrations', 'Registrations'
            else:
                y_col, y_label = 'revenue', 'Revenue (AED)'

            fig.add_trace(go.Scatter(
                x=trend_df['date'],
                y=trend_df[y_col],
                name=y_label,
                line=dict(color=colors['primary'], width=3.5),
                mode='lines+markers',
                marker=dict(size=8, color=colors['secondary']),
                hovertemplate=f'Date: %{{x|%B %Y}}<br>{y_label}: %{{y:,.0f}}'
            ))

            if not use_india and 'sales' in trend_df.columns:
                fig.add_trace(go.Bar(
                    x=trend_df['date'],
                    y=trend_df['sales'],
                    name='Sales (Units)',
                    marker_color='rgba(6, 182, 212, 0.2)',
                    marker_line_color=colors['secondary'],
                    marker_line_width=1.5,
                    yaxis='y2',
                    hovertemplate='Date: %{x|%B %Y}<br>Units: %{y:,}'
                ))

            layout_extra = {}
            if not use_india:
                layout_extra['yaxis2'] = dict(
                    title=dict(text="Units Sold", font=dict(color=colors['secondary'])),
                    overlaying='y', side='right', tickfont=dict(color=colors['secondary'])
                )

            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                hovermode='x unified',
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title=""),
                yaxis=dict(
                    title=dict(text=y_label, font=dict(color=colors['primary'])),
                    showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                    tickfont=dict(color=colors['primary'])
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=0, r=0, t=10, b=0),
                height=380,
                **layout_extra,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No time-series data available for the active filters.")

        st.markdown("<br>", unsafe_allow_html=True)

        # 3. Two columns for breakdown charts
        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown("### Vehicle Category Share")
            if use_india:
                cat_df = get_registrations_by_vehicle_class(session, filters)
                cat_col, val_col = 'vehicle_class', 'registrations'
            else:
                cat_df = get_sales_by_category(session, filters)
                cat_col, val_col = 'vehicle_category', 'revenue'
            if not cat_df.empty:
                fig = px.pie(cat_df, values=val_col, names=cat_col, hole=0.45,
                             color_discrete_sequence=colors['colors_seq'])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                                  font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                                  margin=dict(l=0, r=0, t=20, b=0), height=300)
                fig.update_traces(textposition='inside', textinfo='percent+label',
                                  marker=dict(line=dict(color='#0b0f19', width=2)))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No category data available.")

        with right_col:
            st.markdown("### Fuel Type Distribution")
            if use_india:
                fuel_df = get_registrations_by_fuel(session, filters)
                fuel_y_col, fuel_y_label = 'registrations', 'Registrations'
            else:
                fuel_df = get_sales_by_fuel_type(session, filters)
                fuel_y_col, fuel_y_label = 'sales', 'Units Sold'
            if not fuel_df.empty:
                fig = px.bar(fuel_df, x='fuel_type', y=fuel_y_col, color='fuel_type',
                             color_discrete_sequence=colors['colors_seq'])
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title=fuel_y_label),
                    showlegend=False, margin=dict(l=0, r=0, t=20, b=0), height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No fuel data available.")

        st.markdown("<br>", unsafe_allow_html=True)

        # 4. Regional/Maker distribution
        if use_india:
            st.markdown("### Top Makers by Registrations")
            maker_df = get_registrations_by_maker(session, filters)
            if not maker_df.empty:
                top_makers = maker_df.head(15)
                fig = px.bar(top_makers, x='maker', y='registrations', color='registrations',
                             color_continuous_scale='Viridis',
                             labels={'registrations': 'Registrations', 'maker': 'Maker'})
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Total Registrations"),
                    margin=dict(l=0, r=0, t=20, b=0), height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No maker data available.")
        else:
            st.markdown("### Regional Sales Analytics")
            reg_df = get_sales_by_region(session, filters)
            if not reg_df.empty:
                fig = px.bar(reg_df, x='emirate', y='revenue', color='revenue',
                             color_continuous_scale='Viridis',
                             labels={'revenue': 'Revenue (AED)'})
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Total Revenue"),
                    margin=dict(l=0, r=0, t=20, b=0), height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No regional data available.")
            
    except Exception as e:
        st.error(f"Error rendering Overview Dashboard: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
