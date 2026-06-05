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


def render():
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    tab2, tab3, tab4 = st.tabs([
        "What-If Scenario Engine",
        "Monte Carlo Simulation", "Investment Calculator"
    ])

    # ── Tab 1: NL Advisor (temporarily hidden) ────────────────────
    # with tab1:
    #     st.markdown(section_header("AI Strategy Advisor",
    #                                 "Ask any strategic question about the UAE real estate market"),
    #                 unsafe_allow_html=True)
    #
    #     # Example prompts
    #     st.markdown("**Example Queries:**")
    #     example_prompts = [
    #         "Where should I launch a luxury residential project in 2025?",
    #         "What happens if interest rates increase by 2%?",
    #         "Which area has the highest ROI potential for villa development?",
    #         "What segment should we target next quarter for maximum conversion?",
    #         "Compare Dubai South vs Business Bay for a mid-market apartment project.",
    #     ]
    #     cols = st.columns(len(example_prompts))
    #     selected_prompt = None
    #     for i, (col, prompt) in enumerate(zip(cols, example_prompts)):
    #         with col:
    #             if st.button(f'"{prompt[:40]}…"', key=f"ex_{i}",
    #                           help=prompt,
    #                           use_container_width=True):
    #                 selected_prompt = prompt
    #
    #     # Query input
    #     default_q = selected_prompt or ""
    #     question  = st.text_area(
    #         "Your strategic question",
    #         value=default_q,
    #         height=100,
    #         placeholder="e.g. Which areas in Dubai offer the best risk-adjusted returns in 2025?",
    #         key="ai_q",
    #     )
    #
    #     if st.button("Ask AI Advisor", key="ask_btn", type="primary"):
    #         if question.strip():
    #             with st.spinner("AI is analysing market data …"):
    #                 try:
    #                     result = api.ai_query(question)
    #                     st.markdown(
    #                         f"""<div class="ai-panel">
    #                           <div class="ai-panel-header">
    #                             <span class="ai-badge">AI</span>
    #                             <span class="ai-panel-title">Strategic Analysis</span>
    #                           </div>
    #                           <div class="ai-panel-body">{result.get('answer', '')}</div>
    #                         </div>""",
    #                         unsafe_allow_html=True,
    #                     )
    #                     meta_c1, meta_c2 = st.columns(2)
    #                     meta_c1.caption(f"Context tokens used: {result.get('context_used', 0)}")
    #                     meta_c2.caption(f"RAG active: {result.get('rag_available', False)} | AI: {result.get('ai_available', False)}")
    #                 except api.APIError as e:
    #                     st.error(str(e))
    #         else:
    #             st.warning("Please enter a question.")
    #
    #     # Market Comparison
    #     st.markdown(section_header("Market Comparison"), unsafe_allow_html=True)
    #     comp_areas = st.text_input(
    #         "Areas to compare (comma-separated)",
    #         value="Dubai South,Downtown Dubai,Business Bay,JVC",
    #         key="comp_areas",
    #     )
    #     if st.button("Compare Markets", key="comp_btn"):
    #         with st.spinner("Comparing markets …"):
    #             try:
    #                 comp = api.compare_markets(comp_areas)
    #                 comparisons = comp.get("comparisons", [])
    #                 if comparisons:
    #                     df_comp = pd.DataFrame(comparisons)
    #                     c1, c2 = st.columns([1, 1])
    #                     with c1:
    #                         fig = bar_chart(df_comp["area"].tolist(), df_comp["avg_psf"].tolist(),
    #                                         title="Avg Price / Sqft", horizontal=True,
    #                                         height=280, color=C_INDIGO)
    #                         st.plotly_chart(fig, use_container_width=True)
    #                     with c2:
    #                         fig = bar_chart(df_comp["area"].tolist(), df_comp["rental_yield_pct"].tolist(),
    #                                         title="Rental Yield %", horizontal=True,
    #                                         height=280, color=C_EMERALD)
    #                         st.plotly_chart(fig, use_container_width=True)
    #                     st.markdown(
    #                         f"""<div class="ai-panel"><div class="ai-panel-header">
    #                         <span class="ai-badge">AI</span>
    #                         <span class="ai-panel-title">Comparative Analysis</span></div>
    #                         <div class="ai-panel-body">{comp.get('ai_analysis','')}</div></div>""",
    #                         unsafe_allow_html=True,
    #                     )
    #             except api.APIError as e:
    #                 st.error(str(e))

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
        tcols = st.columns(min(5, len(templates)) or 1)
        selected_template = None
        for i, (tc, tmpl) in enumerate(zip(tcols, templates)):
            with tc:
                if st.button(tmpl["name"], key=f"tmpl_{i}", use_container_width=True):
                    selected_template = tmpl

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
                        default_v = 0.0
                        if selected_template and lv["lever"] in selected_template.get("levers", {}):
                            default_v = float(selected_template["levers"][lv["lever"]])
                        val = st.slider(
                            lv["label"],
                            min_value=-5.0, max_value=10.0,
                            value=default_v, step=0.25,
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
                        result = api.run_scenario(lever_values, horizon,
                                                    selected_template["name"] if selected_template else "Custom")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Demand Change",  f"{result.get('demand_delta_pct',0):+.1f}%")
                        c2.metric("Price Change",   f"{result.get('price_delta_pct',0):+.1f}%")
                        c3.metric("New Demand",     f"{result.get('new_demand',0):,.0f}")
                        c4.metric("New Avg Price",  f"AED {result.get('new_price',0):,.0f}")

                        # Monthly path
                        months = list(range(1, horizon + 1))
                        fig = go.Figure()
                        demand_path = result.get("monthly_path_demand", [])
                        price_path  = result.get("monthly_path_price", [])
                        if demand_path:
                            fig.add_trace(go.Scatter(x=months, y=demand_path, name="Demand",
                                                      line=dict(color=C_INDIGO, width=2.5)))
                        fig.update_layout(**themed(
                            height=320,
                            title="Scenario: Demand Trajectory", xaxis_title="Months"))
                        st.plotly_chart(fig, use_container_width=True)

                        # Lever impacts
                        for lv in result.get("applied_levers", []):
                            d_imp = lv["demand_impact_pct"]
                            p_imp = lv["price_impact_pct"]
                            sev   = "success" if d_imp >= 0 else "warning"
                            st.markdown(
                                alert_card(lv["lever"],
                                            f"Demand impact: {d_imp:+.1f}% | Price impact: {p_imp:+.1f}%",
                                            sev),
                                unsafe_allow_html=True,
                            )

                        ai_analysis = result.get("ai_analysis", "")
                        if ai_analysis:
                            st.markdown(
                                f"""<div class="ai-panel"><div class="ai-panel-header">
                                <span class="ai-badge">AI</span>
                                <span class="ai-panel-title">Scenario Assessment</span></div>
                                <div class="ai-panel-body">{ai_analysis}</div></div>""",
                                unsafe_allow_html=True,
                            )
                    except api.APIError as e:
                        st.error(str(e))
            else:
                st.info("Adjust at least one lever to run the scenario.")

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
                        vals   = [res.get("annual_rental_income_aed",0) * i_years,
                                   res.get("capital_gain_aed", 0)]
                        from frontend.components.charts import pie_chart as pc
                        fig = pc(labels, vals, title="Return Composition", height=280)
                        st.plotly_chart(fig, use_container_width=True)

                    st.markdown(section_header("AI Investment Verdict",
                        help_text="GROQ AI verdict synthesising your financial inputs, area market benchmarks from DLD data, and current macro conditions into a buy / hold / caution recommendation."),
                        unsafe_allow_html=True)
                    verdict = res.get("ai_verdict", "")
                    if verdict:
                        st.markdown(
                            f"""<div class="ai-panel"><div class="ai-panel-header">
                            <span class="ai-badge">AI</span>
                            <span class="ai-panel-title">Investment Assessment</span></div>
                            <div class="ai-panel-body">{verdict}</div></div>""",
                            unsafe_allow_html=True,
                        )
                except api.APIError as e:
                    st.error(str(e))
