"""Tab 6 — AI Strategy Studio (Flagship)"""
from __future__ import annotations

import streamlit as st
import pandas as pd

import frontend.api_client as api
from frontend.components.kpi_cards import (
    kpi_card, render_kpi_row, section_header, alert_card, KPI_CSS
)
from frontend.components.charts import (
    bar_chart, line_chart, monte_carlo_chart
)
from frontend.components.theme import C_INDIGO, C_EMERALD, C_AMBER, C_RED, themed
import plotly.graph_objects as go


def render(filters: dict = None):
    filters = filters or {}
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Latest News",
        "What-If Scenario Engine",
        "Monte Carlo Simulation", "Investment Calculator", "News Forecast"
    ])

    # ── Tab 1: Latest Market News ──────────────────────────────────
    with tab1:
        st.markdown(section_header("UAE Real Estate News",
                                    "Latest news from Google News — last 7 days",
                                    help_text="Sourced from Google News. Select a category, then filter by source to browse headlines. Click any title to open the article in a new tab."),
                    unsafe_allow_html=True)

        NEWS_CATEGORIES = [
            "All", "Market Overview", "Mortgage & Rates", "New Developments",
            "Policy & Regulation", "Investment & ROI", "Infrastructure",
        ]

        col_cat, col_refresh = st.columns([5, 1])
        selected_category = col_cat.selectbox(
            "News category", NEWS_CATEGORIES, index=0, key="news_cat"
        )
        col_refresh.markdown("&nbsp;", unsafe_allow_html=True)
        col_refresh.button("Refresh", key="news_refresh")

        try:
            with st.spinner("Loading latest news …"):
                news_data = api.get_latest_news(selected_category)
            articles  = news_data.get("articles", [])
            api_error = news_data.get("error", "")
        except api.APIError as e:
            articles  = []
            api_error = str(e)

        if api_error:
            st.warning(f"{api_error}")
        elif not articles:
            st.info("No articles found for this category. Try another category or click Refresh.")
        else:
            # Build domain list with "All" as default first option
            seen, domains = set(), []
            for a in articles:
                d = a.get("source", "")
                if d and d not in seen:
                    seen.add(d)
                    domains.append(d)

            selected_domain = st.selectbox(
                "Source", ["All"] + domains, index=0, key="news_domain"
            )

            filtered = articles if selected_domain == "All" else [a for a in articles if a.get("source") == selected_domain]

            links_html = ""
            for a in filtered:
                title    = a.get("title", "Untitled")
                url      = a.get("url", "#")
                raw_date = a.get("publishedAt", "")
                date     = raw_date[:10] if raw_date else ""
                links_html += f"""
                <div style="padding:10px 0 9px; border-bottom:1px solid #e8e8e8;">
                  <div style="font-size:0.72rem; color:#888; margin-bottom:3px;">{date}</div>
                  <a href="{url}" target="_blank" rel="noopener noreferrer"
                     style="font-size:0.95rem; font-weight:600; color:#1a0dab;
                            text-decoration:none; line-height:1.45;">
                    {title}
                  </a>
                </div>"""

            st.markdown(
                f'<div style="max-width:720px;">{links_html}</div>',
                unsafe_allow_html=True,
            )

        # Market Comparison
        st.markdown(section_header("Market Comparison"), unsafe_allow_html=True)
        try:
            _all_areas = api.get_all_areas()
        except api.APIError:
            _all_areas = ["Dubai South", "Downtown Dubai", "Business Bay", "JVC",
                          "Dubai Marina", "JLT", "Palm Jumeirah", "Al Barsha"]
        _default_areas = [a for a in ["Dubai South", "Downtown Dubai", "Business Bay", "JVC"]
                          if a in _all_areas]
        comp_areas_list = st.multiselect(
            "Select areas to compare",
            options=_all_areas,
            default=_default_areas,
            key="comp_areas",
        )
        if st.button("Compare Markets", key="comp_btn"):
            if not comp_areas_list:
                st.warning("Please select at least one area to compare.")
            else:
                with st.spinner("Comparing markets …"):
                    try:
                        comp = api.compare_markets(",".join(comp_areas_list))
                        comparisons = comp.get("comparisons", [])
                        if comparisons:
                            df_comp = pd.DataFrame(comparisons)
                            c1, c2 = st.columns([1, 1])
                            with c1:
                                fig = bar_chart(df_comp["area"].tolist(), df_comp["avg_psf"].tolist(),
                                                title="Avg Price / Sqft", horizontal=True,
                                                height=280, color=C_INDIGO)
                                st.plotly_chart(fig, use_container_width=True)
                            with c2:
                                fig = bar_chart(df_comp["area"].tolist(), df_comp["rental_yield_pct"].tolist(),
                                                title="Rental Yield %", horizontal=True,
                                                height=280, color=C_EMERALD)
                                st.plotly_chart(fig, use_container_width=True)
                            st.markdown(
                                f"""<div class="ai-panel"><div class="ai-panel-header">
                                <span class="ai-badge">AI</span>
                                <span class="ai-panel-title">Comparative Analysis</span></div>
                                <div class="ai-panel-body">{comp.get('ai_analysis','')}</div></div>""",
                                unsafe_allow_html=True,
                            )
                    except api.APIError as e:
                        st.error(str(e))

    # ── Tab 2: What-If Scenario Engine ────────────────────────────
    with tab2:
        st.markdown(section_header("What-If Scenario Engine",
                                    "Adjust market levers to simulate alternative futures",
                                    help_text="Adjust market levers (interest rates, population growth, new supply, sentiment index) to simulate their combined effect on UAE demand and pricing. Horizon up to 24 months forward."),
                    unsafe_allow_html=True)

        # Templates
        try:
            templates = api.get_strategy_templates()
            levers_list = api.get_scenario_levers()
        except api.APIError:
            templates = []
            levers_list = []

        st.markdown("**Quick Templates:**")
        LEVER_MIN, LEVER_MAX = -5.0, 10.0

        def _clamp_lever(v: float) -> float:
            return max(LEVER_MIN, min(LEVER_MAX, float(v)))

        def _apply_levers(levers_list, values: dict, template_defaults: dict) -> None:
            for lv in levers_list:
                key = lv["lever"]
                raw = values.get(key, template_defaults.get(key, 0.0))
                st.session_state[f"lever_{key}"] = _clamp_lever(raw)

        tcols = st.columns(min(5, len(templates)) or 1)
        for i, (tc, tmpl) in enumerate(zip(tcols, templates)):
            with tc:
                if st.button(tmpl["name"], key=f"tmpl_{i}", use_container_width=True,
                             help=tmpl.get("description", "")):
                    area = filters.get("area", "UAE") or "UAE"
                    lever_keys = [lv["lever"] for lv in levers_list]
                    with st.spinner(f"Fetching latest news & calibrating levers for {area}…"):
                        try:
                            cal = api.calibrate_levers_from_news(tmpl["name"], area, lever_keys)
                            calibrated = cal.get("calibrated_levers", {})
                            _apply_levers(levers_list, calibrated, tmpl["levers"])
                            st.session_state["_news_summary"]  = cal.get("news_summary", "") if calibrated else ""
                            st.session_state["_news_articles"] = cal.get("articles", []) if calibrated else []
                        except api.APIError:
                            _apply_levers(levers_list, {}, tmpl["levers"])
                            st.session_state["_news_summary"]  = ""
                            st.session_state["_news_articles"] = []

        if st.session_state.get("_news_summary"):
            st.caption(f"News: {st.session_state['_news_summary']}")

        _news_articles = st.session_state.get("_news_articles", [])
        if _news_articles:
            with st.expander("News used for lever calibration", expanded=True):
                df_news = pd.DataFrame([
                    {
                        "Title":  a.get("title", ""),
                        "Source": a.get("source", ""),
                        "Date":   a.get("publishedAt", "")[:10] if a.get("publishedAt") else "",
                    }
                    for a in _news_articles
                ])
                st.dataframe(df_news, use_container_width=True, hide_index=True)
        elif "_news_articles" in st.session_state:
            st.info("No recent news found for this template — levers set to template defaults.")

        # Lever controls
        st.markdown("**Customise Levers:**")
        lever_values: dict = {}
        if levers_list:
            n_cols = 2
            rows   = [levers_list[i:i+n_cols] for i in range(0, len(levers_list), n_cols)]
            for row in rows:
                cols = st.columns(n_cols)
                for col, lv in zip(cols, row):
                    with col:
                        val = st.slider(
                            lv["label"],
                            min_value=-5.0, max_value=10.0,
                            value=0.0, step=0.25,
                            key=f"lever_{lv['lever']}",
                            help=lv.get("description", ""),
                        )
                        if val != 0:
                            lever_values[lv["lever"]] = val
        else:
            # Fallback manual sliders
            c1, c2 = st.columns(2)
            with c1:
                ir = st.slider("Interest Rate Change (%)", -3.0, 5.0, 0.0, 0.25, key="ir_s")
                if ir != 0:
                    lever_values["interest_rate_change_pct"] = ir
                pop = st.slider("Population Growth Change (%)", -2.0, 5.0, 0.0, 0.25, key="pop_s")
                if pop != 0:
                    lever_values["population_growth_pct"] = pop
            with c2:
                supply = st.slider("New Supply (k units)", -5.0, 20.0, 0.0, 0.5, key="sup_s")
                if supply != 0:
                    lever_values["new_supply_units_k"] = supply
                sent = st.slider("Sentiment Index Change", -30.0, 30.0, 0.0, 1.0, key="sent_s")
                if sent != 0:
                    lever_values["sentiment_change_index"] = sent

        horizon = st.selectbox("Simulation Horizon (months)", [3, 6, 12, 24], index=2, key="sc_horizon")

        if st.button("Run Scenario", key="scenario_btn", type="primary"):
            if lever_values:
                with st.spinner("Running scenario simulation …"):
                    try:
                        result = api.run_scenario(lever_values, horizon, "Custom")
                        st.session_state["_scenario_result"]  = result
                        st.session_state["_scenario_horizon"] = horizon
                    except api.APIError as e:
                        st.error(str(e))
                        st.session_state.pop("_scenario_result", None)
            else:
                st.info("Adjust at least one lever to run the scenario.")

        # Render scenario results + news table from session_state so they
        # persist across reruns (not just on the button-click rerun).
        if st.session_state.get("_scenario_result"):
            result  = st.session_state["_scenario_result"]
            horizon = st.session_state["_scenario_horizon"]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Demand Change", f"{result.get('demand_delta_pct',0):+.1f}%")
            c2.metric("Price Change",  f"{result.get('price_delta_pct',0):+.1f}%")
            c3.metric("New Demand",    f"{result.get('new_demand',0):,.0f}")
            c4.metric("New Avg Price", f"AED {result.get('new_price',0):,.0f}")

            months = list(range(1, horizon + 1))
            fig = go.Figure()
            if result.get("monthly_path_demand"):
                fig.add_trace(go.Scatter(x=months, y=result["monthly_path_demand"],
                                          name="Demand", line=dict(color=C_INDIGO, width=2.5)))
            fig.update_layout(**themed(height=320, title="Scenario: Demand Trajectory",
                                        xaxis_title="Months"))
            st.plotly_chart(fig, use_container_width=True)

            for lv in result.get("applied_levers", []):
                d_imp = lv["demand_impact_pct"]
                p_imp = lv["price_impact_pct"]
                st.markdown(
                    alert_card(lv["lever"],
                               f"Demand impact: {d_imp:+.1f}% | Price impact: {p_imp:+.1f}%",
                               "success" if d_imp >= 0 else "warning"),
                    unsafe_allow_html=True,
                )

            if result.get("ai_analysis"):
                st.markdown(
                    f"""<div class="ai-panel"><div class="ai-panel-header">
                    <span class="ai-badge">AI</span>
                    <span class="ai-panel-title">Scenario Assessment</span></div>
                    <div class="ai-panel-body">{result['ai_analysis']}</div></div>""",
                    unsafe_allow_html=True,
                )


    # ── Tab 3: Monte Carlo ─────────────────────────────────────────
    with tab3:
        st.markdown(section_header("Monte Carlo Simulation",
                                    "Probabilistic demand and price forecast with uncertainty bands",
                                    help_text="Runs N randomised demand and price trajectories based on historical volatility. Outputs P10 (bear case), P50 (base case), and P90 (bull case) scenario bounds over the selected horizon."),
                    unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            mc_demand = st.number_input("Base Monthly Demand", 100.0, 10000.0, 1200.0, step=50.0, key="mc_d")
        with c2:
            mc_price  = st.number_input("Base Avg Price/Sqft (AED)", 500.0, 10000.0, 1400.0, step=50.0, key="mc_p")
        with c3:
            mc_horizon = st.selectbox("Horizon (months)", [6, 12, 24, 36], index=1, key="mc_h")
        with c4:
            mc_vol    = st.slider("Market Volatility", 0.03, 0.25, 0.08, 0.01, key="mc_v")
        mc_sims = st.select_slider("Simulations", [500, 1000, 2000, 5000], value=2000, key="mc_n")

        if st.button("Run Monte Carlo", key="mc_btn", type="primary"):
            with st.spinner(f"Running {mc_sims:,} simulations …"):
                try:
                    result = api.run_monte_carlo(mc_demand, mc_price, mc_horizon, mc_sims, mc_vol)

                    c1, c2, c3 = st.columns(3)
                    df = result["demand_final"]
                    c1.metric("Median Demand (P50)",     f"{df['p50']:,.0f}")
                    c2.metric("Bear Case (P10)",          f"{df['p10']:,.0f}")
                    c3.metric("Bull Case (P90)",          f"{df['p90']:,.0f}")
                    c1.metric("Prob > Base",             f"{df['prob_above_base']:.0f}%")
                    pf = result["price_final"]
                    c2.metric("Median Price (P50)",      f"AED {pf['p50']:,.0f}/sqft")
                    c3.metric("Price Bull (P90)",        f"AED {pf['p90']:,.0f}/sqft")

                    fig_d = monte_carlo_chart(result, metric="demand", height=380)
                    st.plotly_chart(fig_d, use_container_width=True)
                    fig_p = monte_carlo_chart(result, metric="price", height=340)
                    st.plotly_chart(fig_p, use_container_width=True)
                except api.APIError as e:
                    st.error(str(e))

    # ── Tab 4: Investment Calculator ──────────────────────────────
    with tab4:
        st.markdown(section_header("Investment ROI Calculator",
                                    "Full financial analysis with AI verdict",
                                    help_text="Full return-on-investment analysis for a given property. Calculates gross yield, capital gain, annual cash flow, total net return, and payback period based on your input assumptions."),
                    unsafe_allow_html=True)
        with st.form("inv_form"):
            c1, c2 = st.columns(2)
            with c1:
                i_price   = st.number_input("Purchase Price (AED)", 500_000, 100_000_000,
                                             2_000_000, step=100_000, key="i_price")
                i_sqft    = st.number_input("Property Size (sqft)", 300, 20000, 1200, step=50, key="i_sqft")
                i_yield   = st.number_input("Expected Rental Yield (%)", 1.0, 15.0, 6.5, step=0.1, key="i_yield")
                i_years   = st.number_input("Holding Period (years)", 1, 20, 5, key="i_years")
            with c2:
                i_apprc   = st.number_input("Expected Annual Appreciation (%)", 0.0, 20.0, 5.0, step=0.5, key="i_apprc")
                i_finance = st.slider("Financing (%)", 0, 80, 0, key="i_finance")
                i_mort    = st.number_input("Mortgage Rate (%)", 1.0, 10.0, 4.0, step=0.25, key="i_mort")
            submitted = st.form_submit_button("Calculate ROI")

        if submitted:
            with st.spinner("Calculating investment returns …"):
                try:
                    res = api.run_investment_analysis(
                        i_price, float(i_sqft), i_yield, i_years,
                        i_apprc, float(i_finance), i_mort,
                    )
                    st.session_state["inv_result"] = res
                    st.session_state["inv_params"] = {
                        "price": i_price, "yield_pct": i_yield,
                        "years": i_years,
                    }
                    st.session_state.pop("inv_verdict", None)
                except api.APIError as e:
                    st.error(str(e))

        res = st.session_state.get("inv_result")
        if res:
            params = st.session_state.get("inv_params", {})
            render_kpi_row([
                kpi_card("Total ROI", f"{res.get('total_roi_pct',0):.1f}",
                          None, suffix="%",
                          gradient="emerald" if res.get("total_roi_pct",0)>20 else "amber",
                          help_text="Total return on invested equity over the full holding period: (rental income + capital gain − costs) ÷ equity invested × 100. Covers your selected holding period."),
                kpi_card("Annualised ROI", f"{res.get('annualised_roi_pct',0):.1f}",
                          None, suffix="%", gradient="indigo",
                          help_text="Compound annual growth rate of your total return over the holding period. Useful for comparing this investment to other asset classes on an apples-to-apples basis."),
                kpi_card("Total Return", f"{res.get('total_return_aed',0)/1e6:.1f}M",
                          None, prefix="AED ", gradient="emerald",
                          help_text="Absolute AED return over the holding period = cumulative rental income + capital gain on exit. Does not account for financing costs unless a mortgage rate is entered."),
                kpi_card("Payback Period", f"{res.get('payback_years',0):.1f}",
                          None, suffix=" yrs", gradient="violet",
                          help_text="Years required for cumulative rental income to recover the initial equity outlay. Shorter payback indicates a higher-yielding or lower-leverage investment."),
            ], cols=4)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Financial Breakdown**")
                breakdown = {
                    "Purchase Price":        f"AED {res.get('purchase_price_aed',0):,.0f}",
                    "Equity Required":       f"AED {res.get('equity_required_aed',0):,.0f}",
                    "Annual Rental Income":  f"AED {res.get('annual_rental_income_aed',0):,.0f}",
                    "Annual Cash Flow":      f"AED {res.get('annual_cashflow_aed',0):,.0f}",
                    "Exit Value":            f"AED {res.get('exit_value_aed',0):,.0f}",
                    "Capital Gain":          f"AED {res.get('capital_gain_aed',0):,.0f}",
                }
                df_bd = pd.DataFrame.from_dict(breakdown, orient="index", columns=["Value"])
                st.dataframe(df_bd, use_container_width=True)

            with c2:
                labels = ["Rental Income", "Capital Gain"]
                vals   = [res.get("annual_rental_income_aed",0) * params.get("years", 1),
                           res.get("capital_gain_aed", 0)]
                from frontend.components.charts import pie_chart as pc
                fig = pc(labels, vals, title="Return Composition", height=280)
                st.plotly_chart(fig, use_container_width=True)

            st.markdown(section_header("AI Investment Verdict",
                help_text="GROQ AI verdict synthesising your financial inputs and current macro conditions into a buy / hold / caution recommendation."),
                unsafe_allow_html=True)

            verdict = st.session_state.get("inv_verdict")
            if verdict:
                st.markdown(
                    f"""<div class="ai-panel"><div class="ai-panel-header">
                    <span class="ai-badge">AI</span>
                    <span class="ai-panel-title">Investment Assessment</span></div>
                    <div class="ai-panel-body">{verdict}</div></div>""",
                    unsafe_allow_html=True,
                )
            elif st.button("Get AI Verdict", key="verdict_btn", type="secondary"):
                with st.spinner("Asking AI for investment verdict …"):
                    try:
                        vres = api.get_investment_verdict(
                            params.get("price", 0),
                            params.get("yield_pct", 0),
                            params.get("years", 5),
                            res.get("total_roi_pct", 0),
                            res.get("annualised_roi_pct", 0),
                        )
                        st.session_state["inv_verdict"] = vres.get("ai_verdict", "")
                        st.rerun()
                    except api.APIError as e:
                        st.error(str(e))

    # ── Tab 5: News Forecast ───────────────────────────────────────
    with tab5:
        st.markdown(section_header(
            "News-Augmented Forecast",
            "AI prediction based on last 15 days of news",
            help_text="Fetches the latest UAE real estate news across all categories, sends them to Groq AI to extract a market sentiment score and key signals, then applies those signals through the scenario engine to produce a news-adjusted demand and price forecast."),
            unsafe_allow_html=True)

        _, col_refresh = st.columns([6, 1])
        col_refresh.markdown("&nbsp;", unsafe_allow_html=True)
        if col_refresh.button("Refresh", key="nf_refresh"):
            st.session_state.pop("_news_forecast", None)

        if "_news_forecast" not in st.session_state:
            with st.spinner("Analysing latest news with AI…"):
                try:
                    st.session_state["_news_forecast"] = api.get_news_forecast()
                except api.APIError as e:
                    st.session_state["_news_forecast"] = {"error": str(e)}

        nf = st.session_state.get("_news_forecast", {})

        if nf.get("error") and not nf.get("key_signals"):
            st.warning(nf["error"])
        else:
            if nf.get("error"):
                st.warning(nf["error"])

            # ── Row 1: Sentiment score + key signals ───────────────
            score  = nf.get("sentiment_score", 50)
            label  = nf.get("sentiment_label", "Neutral")
            badge_type = "success" if label == "Bullish" else ("warning" if label == "Bearish" else "info")

            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("Market Sentiment", f"{score} / 100")
                st.markdown(
                    alert_card(label, f"Based on {nf.get('articles_used', 0)} news articles", badge_type),
                    unsafe_allow_html=True,
                )
            with c2:
                signals = nf.get("key_signals", [])
                if signals:
                    st.markdown("**Key Market Signals Detected:**")
                    for s in signals:
                        st.markdown(f"• {s}")
                else:
                    st.info("No key signals extracted.")

            st.divider()

            # ── Row 2: Demand delta + chart ────────────────────────
            demand_delta = nf.get("demand_delta_pct", 0.0)
            price_delta  = nf.get("price_delta_pct",  0.0)
            months       = list(range(1, len(nf.get("monthly_path_demand", [])) + 1))

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Demand Adjustment", f"{demand_delta:+.1f}%",
                          delta=f"vs base {nf.get('base_demand', 0):,.0f} units/month")
                fig_d = go.Figure()
                fig_d.add_trace(go.Scatter(
                    x=months,
                    y=[nf.get("base_demand", 0)] * len(months),
                    name="Base Forecast", line=dict(color="#9ca3af", dash="dash", width=2),
                ))
                fig_d.add_trace(go.Scatter(
                    x=months, y=nf.get("monthly_path_demand", []),
                    name="News-Adjusted", line=dict(color=C_INDIGO, width=2.5),
                    fill="tonexty", fillcolor="rgba(99,102,241,0.08)",
                ))
                fig_d.update_layout(**themed(height=280, title="Demand: Base vs News-Adjusted",
                                             xaxis_title="Month"))
                st.plotly_chart(fig_d, use_container_width=True)

            with c2:
                st.metric("Price Adjustment", f"{price_delta:+.1f}%",
                          delta=f"vs base AED {nf.get('base_price', 0):,.0f}/sqft")
                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(
                    x=months,
                    y=[nf.get("base_price", 0)] * len(months),
                    name="Base Forecast", line=dict(color="#9ca3af", dash="dash", width=2),
                ))
                fig_p.add_trace(go.Scatter(
                    x=months, y=nf.get("monthly_path_price", []),
                    name="News-Adjusted", line=dict(color=C_EMERALD, width=2.5),
                    fill="tonexty", fillcolor="rgba(16,185,129,0.08)",
                ))
                fig_p.update_layout(**themed(height=280, title="Price: Base vs News-Adjusted",
                                             xaxis_title="Month"))
                st.plotly_chart(fig_p, use_container_width=True)

            # ── Row 3: Articles table ──────────────────────────────
            articles = nf.get("articles", [])
            if articles:
                with st.expander(f"News articles analysed ({len(articles)})", expanded=False):
                    df_arts = pd.DataFrame([
                        {
                            "Title":  a.get("title", ""),
                            "Source": a.get("source", ""),
                            "Date":   a.get("publishedAt", "")[:10] if a.get("publishedAt") else "",
                        }
                        for a in articles
                    ])
                    st.dataframe(df_arts, use_container_width=True, hide_index=True)
