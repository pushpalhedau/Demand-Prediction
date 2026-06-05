"""
Scenario Engine — Monte Carlo simulation, What-If analysis, and counterfactual scenarios.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Empirical impact coefficients derived from UAE market research
LEVER_IMPACTS = {
    "interest_rate_change_pct":    {"demand": -3.5, "price": -2.0},
    "population_growth_pct":       {"demand":  5.0, "price":  3.0},
    "gdp_growth_pct":              {"demand":  2.5, "price":  1.5},
    "visa_policy_change":          {"demand":  8.0, "price":  4.0},   # golden visa expansion
    "new_supply_units_k":          {"demand": -0.5, "price": -1.2},
    "oil_price_change_pct":        {"demand":  0.8, "price":  0.5},
    "sentiment_change_index":      {"demand":  1.2, "price":  0.8},
    "infrastructure_investment_bn": {"demand": 2.0, "price": 1.8},
}


class ScenarioEngine:

    def what_if(self, levers: Dict[str, float],
                base_demand: float, base_price: float,
                horizon_months: int = 12) -> Dict:
        """
        Apply lever changes to base demand and price.
        levers: {lever_name: change_magnitude}
        """
        demand_delta_pct = 0.0
        price_delta_pct  = 0.0
        applied = []
        for lever, magnitude in levers.items():
            if lever in LEVER_IMPACTS:
                coeff = LEVER_IMPACTS[lever]
                d_impact = coeff["demand"] * magnitude
                p_impact = coeff["price"]  * magnitude
                demand_delta_pct += d_impact
                price_delta_pct  += p_impact
                applied.append({
                    "lever": lever.replace("_", " ").title(),
                    "magnitude": magnitude,
                    "demand_impact_pct": round(d_impact, 2),
                    "price_impact_pct":  round(p_impact, 2),
                })

        new_demand = base_demand * (1 + demand_delta_pct / 100)
        new_price  = base_price  * (1 + price_delta_pct  / 100)

        # Monthly path with decay
        monthly_demand = []
        monthly_price  = []
        decay = 0.85
        cur_d = base_demand
        cur_p = base_price
        step_d = (new_demand - base_demand) / horizon_months
        step_p = (new_price  - base_price)  / horizon_months
        for i in range(1, horizon_months + 1):
            cur_d += step_d * (decay ** i)
            cur_p += step_p * (decay ** i)
            monthly_demand.append(round(max(0, cur_d), 1))
            monthly_price.append(round(max(0, cur_p), 0))

        return {
            "base_demand":       round(base_demand, 1),
            "base_price":        round(base_price, 0),
            "new_demand":        round(new_demand, 1),
            "new_price":         round(new_price, 0),
            "demand_delta_pct":  round(demand_delta_pct, 2),
            "price_delta_pct":   round(price_delta_pct, 2),
            "applied_levers":    applied,
            "monthly_path_demand": monthly_demand,
            "monthly_path_price":  monthly_price,
            "summary": self._scenario_summary(demand_delta_pct, price_delta_pct, applied),
        }

    def monte_carlo(
        self,
        base_demand: float,
        base_price: float,
        horizon_months: int = 12,
        n_simulations: int = 5000,
        volatility: float = 0.08,
    ) -> Dict:
        """
        Run N Monte Carlo simulations with GBM (Geometric Brownian Motion).
        Returns percentile bands for demand and price forecasts.
        """
        rng = np.random.default_rng(42)
        dt  = 1 / 12  # monthly steps
        mu_demand = 0.005   # slight positive drift (UAE market trend)
        mu_price  = 0.003
        sigma = volatility

        # Simulate all paths at once
        rand_d = rng.standard_normal((n_simulations, horizon_months))
        rand_p = rng.standard_normal((n_simulations, horizon_months))

        demand_paths = np.zeros((n_simulations, horizon_months))
        price_paths  = np.zeros((n_simulations, horizon_months))
        demand_paths[:, 0] = base_demand * np.exp((mu_demand - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rand_d[:, 0])
        price_paths[:, 0]  = base_price  * np.exp((mu_price  - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rand_p[:, 0])

        for t in range(1, horizon_months):
            demand_paths[:, t] = demand_paths[:, t-1] * np.exp(
                (mu_demand - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rand_d[:, t])
            price_paths[:, t]  = price_paths[:, t-1]  * np.exp(
                (mu_price  - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rand_p[:, t])

        def pcts(arr):
            return {
                "p10": np.percentile(arr, 10, axis=0).round(1).tolist(),
                "p25": np.percentile(arr, 25, axis=0).round(1).tolist(),
                "p50": np.percentile(arr, 50, axis=0).round(1).tolist(),
                "p75": np.percentile(arr, 75, axis=0).round(1).tolist(),
                "p90": np.percentile(arr, 90, axis=0).round(1).tolist(),
            }

        final_demand = demand_paths[:, -1]
        final_price  = price_paths[:, -1]

        return {
            "n_simulations":     n_simulations,
            "horizon_months":    horizon_months,
            "demand_paths":      pcts(demand_paths),
            "price_paths":       pcts(price_paths),
            "demand_final": {
                "mean":  round(float(np.mean(final_demand)), 1),
                "p10":   round(float(np.percentile(final_demand, 10)), 1),
                "p50":   round(float(np.percentile(final_demand, 50)), 1),
                "p90":   round(float(np.percentile(final_demand, 90)), 1),
                "prob_above_base": round(float((final_demand > base_demand).mean()) * 100, 1),
            },
            "price_final": {
                "mean":  round(float(np.mean(final_price)), 0),
                "p10":   round(float(np.percentile(final_price, 10)), 0),
                "p50":   round(float(np.percentile(final_price, 50)), 0),
                "p90":   round(float(np.percentile(final_price, 90)), 0),
                "prob_above_base": round(float((final_price > base_price).mean()) * 100, 1),
            },
        }

    def investment_analysis(
        self,
        purchase_price_aed: float,
        area_sqft: float,
        rental_yield_pct: float,
        holding_years: int = 5,
        appreciation_pct: float = 5.0,
        financing_pct: float = 0.0,
        mortgage_rate_pct: float = 4.0,
    ) -> Dict:
        equity = purchase_price_aed * (1 - financing_pct / 100)
        loan   = purchase_price_aed * (financing_pct / 100)
        annual_rental_income = purchase_price_aed * (rental_yield_pct / 100)
        annual_appreciation  = purchase_price_aed * (appreciation_pct / 100)
        annual_mortgage_cost = loan * (mortgage_rate_pct / 100) if loan > 0 else 0
        net_annual_cashflow  = annual_rental_income - annual_mortgage_cost

        # DLD fees ~4% of purchase price
        acquisition_cost = purchase_price_aed * 0.04
        exit_value = purchase_price_aed * ((1 + appreciation_pct / 100) ** holding_years)
        total_rental = net_annual_cashflow * holding_years
        capital_gain  = exit_value - purchase_price_aed
        total_return  = total_rental + capital_gain - acquisition_cost
        roi_pct = (total_return / equity) * 100 if equity > 0 else 0
        irr_approx = (roi_pct / holding_years)

        return {
            "purchase_price_aed":   round(purchase_price_aed, 0),
            "equity_required_aed":  round(equity + acquisition_cost, 0),
            "annual_rental_income_aed": round(annual_rental_income, 0),
            "annual_cashflow_aed":  round(net_annual_cashflow, 0),
            "exit_value_aed":       round(exit_value, 0),
            "capital_gain_aed":     round(capital_gain, 0),
            "total_return_aed":     round(total_return, 0),
            "total_roi_pct":        round(roi_pct, 1),
            "annualised_roi_pct":   round(irr_approx, 2),
            "rental_yield_pct":     round(rental_yield_pct, 2),
            "payback_years":        round(equity / annual_rental_income, 1) if annual_rental_income > 0 else 99,
        }

    @staticmethod
    def _scenario_summary(demand_delta: float, price_delta: float, levers: List[Dict]) -> str:
        d_str = f"+{demand_delta:.1f}%" if demand_delta >= 0 else f"{demand_delta:.1f}%"
        p_str = f"+{price_delta:.1f}%" if price_delta >= 0 else f"{price_delta:.1f}%"
        top_lever = levers[0]["lever"] if levers else "market conditions"
        return (f"Under this scenario, demand is expected to shift {d_str} and prices {p_str} "
                f"over the forecast horizon. Primary driver: {top_lever}.")


scenario_engine = ScenarioEngine()
