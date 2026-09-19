"""
What-if response model for the demand forecast: how a change in one market lever moves demand.

Levers are applied one at a time, relative to the recent baseline. Fuel and crude are ELASTICITIES
(% change in units per +1% change in price), so they hold in any currency; an absolute "per +1
currency unit" figure would not. Crude is upstream of the pump price, so its direct effect is
deliberately mild to avoid double-counting the petrol/diesel move it usually feeds. Loan APR is the
% change in units per +1 percentage point.
    crude oil   ~ -0.12% units per +1% price
    petrol      ~ -0.08% units per +1% price
    diesel      ~ -0.05% units per +1% price  (pickup / commercial buyers)
    loan APR    ~ -3%    units per +1pt
"""

RELATIVE_ELASTICITY = {
    "crude_oil_price_usd": -0.12,
    "petrol_price_per_litre": -0.08,
    "diesel_price_per_litre": -0.05,
}
POINT_RESPONSE = {"auto_loan_apr_pct": -3.0}
LOAN_MONTHS = 60


def supply_drag_pct(days_supply: float) -> float:
    """Percent of demand lost to thin stock: zero at/above ~55 days' supply, ~-1.1%/day below it."""
    if days_supply >= 55:
        return 0.0
    return (days_supply - 55) * 1.1


def monthly_payment(apr_pct: float, loan: float) -> float:
    """Level monthly payment on `loan` over LOAN_MONTHS at the given APR."""
    r = apr_pct / 100 / 12
    if r <= 0:
        return loan / LOAN_MONTHS
    return loan * r / (1 - (1 + r) ** -LOAN_MONTHS)


def net_response_pct(overrides: dict, factor_stats: dict) -> float:
    """Combine the active levers into one % shift in demand versus the recent baseline."""
    if not overrides or not factor_stats:
        return 0.0
    pct = 0.0
    for col, val in overrides.items():
        if col not in factor_stats:
            continue
        base = factor_stats[col]["last"]
        if col == "inventory_days_supply":
            pct += supply_drag_pct(float(val)) - supply_drag_pct(float(base))
        elif col in RELATIVE_ELASTICITY and float(base) > 0:
            pct += (float(val) / float(base) - 1) * 100 * RELATIVE_ELASTICITY[col]
        elif col in POINT_RESPONSE:
            pct += (float(val) - float(base)) * POINT_RESPONSE[col]
    return pct
