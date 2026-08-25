"""
Alternative vehicle placement engine.

When the exact car a customer asked for is not available, this ranks the units
the network *does* have. A recommendation has to satisfy three constraints at
once, and scoring only the first is what makes most "similar vehicles" widgets
useless on a showroom floor:

  1. Similarity      — is it actually the same car to this shopper?
  2. Availability    — can they take delivery, and how soon?
  3. Business value  — does placing it help the store?

The third is what turns a lookup into a recommendation: given two equally good
substitutes, the one that has been sitting on the lot for 90 days is the one
worth putting in front of the customer.
"""

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Cross-shopping affinity between body styles.
#
# Segments are not equidistant. A Minivan shopper will look at a three-row SUV
# but never at a Coupe, and a Sedan shopper will consider a Hatchback long
# before a Pickup. These weights encode how real cross-shopping behaves.
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_AFFINITY = {
    ("SUV", "SUV"): 1.00, ("SUV", "Minivan"): 0.55, ("SUV", "Pickup"): 0.40,
    ("SUV", "Sedan"): 0.45, ("SUV", "Hatchback"): 0.35, ("SUV", "Luxury"): 0.50,
    ("SUV", "Coupe"): 0.15,
    ("Sedan", "Sedan"): 1.00, ("Sedan", "Hatchback"): 0.70, ("Sedan", "SUV"): 0.45,
    ("Sedan", "Luxury"): 0.55, ("Sedan", "Coupe"): 0.40, ("Sedan", "Minivan"): 0.20,
    ("Sedan", "Pickup"): 0.10,
    ("Pickup", "Pickup"): 1.00, ("Pickup", "SUV"): 0.40, ("Pickup", "Minivan"): 0.15,
    ("Pickup", "Sedan"): 0.10, ("Pickup", "Hatchback"): 0.05,
    ("Pickup", "Luxury"): 0.15, ("Pickup", "Coupe"): 0.10,
    ("Luxury", "Luxury"): 1.00, ("Luxury", "SUV"): 0.50, ("Luxury", "Sedan"): 0.55,
    ("Luxury", "Coupe"): 0.45, ("Luxury", "Hatchback"): 0.20,
    ("Luxury", "Minivan"): 0.15, ("Luxury", "Pickup"): 0.15,
    ("Hatchback", "Hatchback"): 1.00, ("Hatchback", "Sedan"): 0.70,
    ("Hatchback", "SUV"): 0.35, ("Hatchback", "Coupe"): 0.30,
    ("Hatchback", "Luxury"): 0.20, ("Hatchback", "Minivan"): 0.15,
    ("Hatchback", "Pickup"): 0.05,
    ("Minivan", "Minivan"): 1.00, ("Minivan", "SUV"): 0.60, ("Minivan", "Sedan"): 0.20,
    ("Minivan", "Hatchback"): 0.15, ("Minivan", "Luxury"): 0.15,
    ("Minivan", "Pickup"): 0.15, ("Minivan", "Coupe"): 0.05,
    ("Coupe", "Coupe"): 1.00, ("Coupe", "Luxury"): 0.45, ("Coupe", "Sedan"): 0.40,
    ("Coupe", "Hatchback"): 0.30, ("Coupe", "SUV"): 0.15,
    ("Coupe", "Pickup"): 0.10, ("Coupe", "Minivan"): 0.05,
}

# Powertrain switching. A shopper on an EV may accept a hybrid, but someone who
# came in for a gas car is rarely ready to change how they refuel.
FUEL_AFFINITY = {
    ("Gasoline", "Gasoline"): 1.00, ("Gasoline", "Hybrid"): 0.80,
    ("Gasoline", "Diesel"): 0.55, ("Gasoline", "Electric"): 0.30,
    ("Hybrid", "Hybrid"): 1.00, ("Hybrid", "Gasoline"): 0.80,
    ("Hybrid", "Electric"): 0.60, ("Hybrid", "Diesel"): 0.40,
    ("Electric", "Electric"): 1.00, ("Electric", "Hybrid"): 0.65,
    ("Electric", "Gasoline"): 0.25, ("Electric", "Diesel"): 0.15,
    ("Diesel", "Diesel"): 1.00, ("Diesel", "Gasoline"): 0.60,
    ("Diesel", "Hybrid"): 0.40, ("Diesel", "Electric"): 0.20,
}

# How much each attribute contributes to the similarity half of the score.
SIMILARITY_WEIGHTS = {
    "category": 0.26,
    "price": 0.24,
    "fuel": 0.14,
    "seats": 0.10,
    "power": 0.09,
    "drive": 0.07,
    "brand": 0.05,
    "market": 0.05,
}

# Availability tiers, best first. A car the customer can drive home today is
# worth far more than one that needs an eight-week factory order.
AVAILABILITY_TIERS = {
    "in_stock_here": 1.00,
    "in_stock_nearby": 0.78,
    "in_transit": 0.55,
    "lease_return_soon": 0.42,
    "unavailable": 0.00,
}

# Final blend across the three constraints.
SCORE_WEIGHTS = {"similarity": 0.55, "availability": 0.30, "business": 0.15}

EARTH_RADIUS_MILES = 3958.8


def _haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles between two coordinate arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _affinity(table, a, b, default=0.2):
    """Symmetric lookup into an affinity table."""
    return table.get((a, b), table.get((b, a), default))


def compute_similarity(target: pd.Series, candidates: pd.DataFrame,
                       market_share: pd.Series = None) -> pd.DataFrame:
    """
    Score how close each candidate is to the requested vehicle, 0-1.

    `market_share` optionally carries revealed cross-shopping demand (how much
    each model actually sells in the target's segment), which nudges the
    ranking toward pairs real buyers genuinely consider.
    """
    out = candidates.copy()

    out["sim_category"] = [
        _affinity(CATEGORY_AFFINITY, target["category"], c) for c in out["category"]
    ]
    out["sim_fuel"] = [
        _affinity(FUEL_AFFINITY, target["fuel_type"], f) for f in out["fuel_type"]
    ]

    # Price tolerance: a shopper stretches a few thousand dollars, not tens of
    # thousands, so similarity decays exponentially rather than linearly.
    target_price = float(target["price_usd"]) or 1.0
    price_gap = (out["price_usd"].astype(float) - target_price).abs()
    out["sim_price"] = np.exp(-price_gap / (target_price * 0.22))

    # Seating is close to a hard requirement — a family that needs three rows
    # cannot take a five-seater.
    seat_gap = (out["seating_capacity"].fillna(5) - float(target["seating_capacity"] or 5)).abs()
    out["sim_seats"] = np.clip(1.0 - seat_gap * 0.35, 0, 1)

    target_hp = float(target["horsepower"] or 200)
    hp_gap = (out["horsepower"].astype(float).fillna(target_hp) - target_hp).abs()
    out["sim_power"] = np.exp(-hp_gap / max(target_hp * 0.45, 1))

    out["sim_drive"] = np.where(out["drive_type"] == target["drive_type"], 1.0, 0.55)
    out["sim_brand"] = np.where(out["brand"] == target["brand"], 1.0, 0.45)

    if market_share is not None and len(market_share) > 0:
        shares = out["model"].map(market_share).fillna(0.0)
        denom = float(shares.max()) or 1.0
        out["sim_market"] = shares / denom
    else:
        out["sim_market"] = 0.5

    w = SIMILARITY_WEIGHTS
    out["similarity"] = (
        w["category"] * out["sim_category"]
        + w["price"] * out["sim_price"]
        + w["fuel"] * out["sim_fuel"]
        + w["seats"] * out["sim_seats"]
        + w["power"] * out["sim_power"]
        + w["drive"] * out["sim_drive"]
        + w["brand"] * out["sim_brand"]
        + w["market"] * out["sim_market"]
    )
    return out


def attach_availability(candidates: pd.DataFrame, snapshot: pd.DataFrame,
                        dealer_id: str = None, dealers: pd.DataFrame = None,
                        lease_returns: pd.DataFrame = None,
                        max_miles: float = 150.0) -> pd.DataFrame:
    """
    Resolve where each candidate physically is, and how soon it can be had.

    Walks the four tiers in order of desirability and keeps the best hit per
    vehicle: on this lot, at a nearby store, inbound in transit, or returning
    off lease within the next 30 days.
    """
    out = candidates.copy()
    out["availability"] = "unavailable"
    out["availability_detail"] = "Factory order required"
    out["units_available"] = 0
    out["source_dealer"] = None
    out["distance_miles"] = np.nan
    out["days_in_stock"] = np.nan
    out["holding_cost_usd"] = 0.0

    if snapshot is None or snapshot.empty:
        return out

    home = None
    if dealer_id and dealers is not None and not dealers.empty:
        match = dealers[dealers["dealer_id"] == dealer_id]
        if not match.empty:
            home = match.iloc[0]

    in_stock = snapshot[snapshot["current_stock"] > 0]

    for idx, row in out.iterrows():
        vid = row["vehicle_id"]
        lines = in_stock[in_stock["vehicle_id"] == vid]

        # Tier 1 — sitting on the requesting store's lot.
        here = lines[lines["dealer_id"] == dealer_id] if dealer_id else lines.iloc[0:0]
        if not here.empty:
            best = here.sort_values("days_in_stock", ascending=False).iloc[0]
            out.at[idx, "availability"] = "in_stock_here"
            out.at[idx, "availability_detail"] = "On your lot now"
            out.at[idx, "units_available"] = int(here["current_stock"].sum())
            out.at[idx, "source_dealer"] = best.get("dealer_name")
            out.at[idx, "distance_miles"] = 0.0
            out.at[idx, "days_in_stock"] = best["days_in_stock"]
            out.at[idx, "holding_cost_usd"] = float(best["estimated_holding_cost_usd"])
            continue

        # Tier 2 — at another store within driving range.
        others = lines[lines["dealer_id"] != dealer_id] if dealer_id else lines
        if not others.empty:
            cand = others.copy()
            if home is not None and pd.notnull(home.get("latitude")):
                cand["distance_miles"] = _haversine_miles(
                    float(home["latitude"]), float(home["longitude"]),
                    cand["latitude"].astype(float), cand["longitude"].astype(float),
                )
                cand = cand[cand["distance_miles"] <= max_miles]
            else:
                cand["distance_miles"] = np.nan

            if not cand.empty:
                best = cand.sort_values(
                    ["distance_miles", "days_in_stock"], ascending=[True, False]
                ).iloc[0]
                dist = best["distance_miles"]
                detail = (f"{best['dealer_name']} ({dist:.0f} mi away)"
                          if pd.notnull(dist) else f"{best['dealer_name']}")
                out.at[idx, "availability"] = "in_stock_nearby"
                out.at[idx, "availability_detail"] = detail
                out.at[idx, "units_available"] = int(cand["current_stock"].sum())
                out.at[idx, "source_dealer"] = best.get("dealer_name")
                out.at[idx, "distance_miles"] = dist
                out.at[idx, "days_in_stock"] = best["days_in_stock"]
                out.at[idx, "holding_cost_usd"] = float(best["estimated_holding_cost_usd"])
                continue

        # Tier 3 — already on a truck or a boat.
        transit = snapshot[(snapshot["vehicle_id"] == vid) & (snapshot["transit_stock"] > 0)]
        if dealer_id and not transit.empty:
            mine = transit[transit["dealer_id"] == dealer_id]
            transit = mine if not mine.empty else transit
        if not transit.empty:
            best = transit.iloc[0]
            eta = int(best.get("supplier_lead_time_days") or 30)
            out.at[idx, "availability"] = "in_transit"
            out.at[idx, "availability_detail"] = f"In transit — ETA ~{eta} days"
            out.at[idx, "units_available"] = int(transit["transit_stock"].sum())
            out.at[idx, "source_dealer"] = best.get("dealer_name")
            continue

        # Tier 4 — coming back off lease shortly. This tier only exists because
        # the lease book is modelled; it is supply the network already owns.
        if lease_returns is not None and not lease_returns.empty:
            soon = lease_returns[lease_returns["vehicle_id"] == vid]
            if dealer_id and not soon.empty and "dealer_id" in soon.columns:
                mine = soon[soon["dealer_id"] == dealer_id]
                soon = mine if not mine.empty else soon
            if not soon.empty:
                nxt = pd.to_datetime(soon["lease_maturity_date"]).min()
                days = max((nxt - pd.Timestamp.today()).days, 0)
                if days <= 45:
                    out.at[idx, "availability"] = "lease_return_soon"
                    out.at[idx, "availability_detail"] = (
                        f"Lease return in ~{days} days ({len(soon)} unit(s))"
                    )
                    out.at[idx, "units_available"] = int(len(soon))
                    continue

    out["availability_score"] = out["availability"].map(AVAILABILITY_TIERS).fillna(0.0)
    return out


def compute_business_priority(candidates: pd.DataFrame) -> pd.DataFrame:
    """
    Reward substitutes the store genuinely wants to move.

    Aging is the dominant term: a unit at 90+ days is burning floorplan every
    day it stays, so placing it is worth materially more than placing fresh
    stock that would have sold anyway.
    """
    out = candidates.copy()
    days = out["days_in_stock"].fillna(0)
    aging = np.clip(days / 120.0, 0, 1)
    depth = np.clip(out["units_available"].fillna(0) / 8.0, 0, 1)
    out["business_priority"] = np.clip(0.65 * aging + 0.35 * depth, 0, 1)
    return out


def recommend_alternatives(target_vehicle: pd.Series, catalog: pd.DataFrame,
                           snapshot: pd.DataFrame, dealers: pd.DataFrame = None,
                           dealer_id: str = None, lease_returns: pd.DataFrame = None,
                           market_share: pd.Series = None, top_n: int = 6,
                           include_unavailable: bool = False,
                           max_miles: float = 150.0) -> pd.DataFrame:
    """
    Rank substitute vehicles for an unavailable request.

    Returns a scored frame with the reasoning attached, so the salesperson can
    see why each car was put forward rather than being handed a bare list.
    """
    candidates = catalog[catalog["vehicle_id"] != target_vehicle["vehicle_id"]].copy()
    if candidates.empty:
        return candidates

    scored = compute_similarity(target_vehicle, candidates, market_share=market_share)
    scored = attach_availability(
        scored, snapshot, dealer_id=dealer_id, dealers=dealers,
        lease_returns=lease_returns, max_miles=max_miles,
    )
    scored = compute_business_priority(scored)

    if not include_unavailable:
        scored = scored[scored["availability"] != "unavailable"]
        if scored.empty:
            return scored

    w = SCORE_WEIGHTS
    scored["match_score"] = (
        w["similarity"] * scored["similarity"]
        + w["availability"] * scored["availability_score"]
        + w["business"] * scored["business_priority"]
    )
    # Two distinct numbers, because they answer different questions: the
    # placement score drives the ranking (it accounts for how fast the customer
    # can actually get the car), while spec match answers "is this the same
    # car?". Showing only the second makes the ordering look wrong when a
    # perfect spec match sits 100 miles away.
    scored["placement_score_pct"] = (scored["match_score"] * 100).round(0)
    scored["match_pct"] = (scored["similarity"] * 100).round(0)
    scored["price_delta_usd"] = (
        scored["price_usd"].astype(float) - float(target_vehicle["price_usd"])
    )
    scored["match_reasons"] = scored.apply(
        lambda r: _explain(target_vehicle, r), axis=1
    )
    scored["tradeoffs"] = scored.apply(lambda r: _tradeoffs(target_vehicle, r), axis=1)

    return scored.sort_values("match_score", ascending=False).head(top_n)


def _explain(target: pd.Series, row: pd.Series) -> str:
    """Plain-language list of what this substitute has in common with the request."""
    reasons = []
    if row["category"] == target["category"]:
        reasons.append(f"same {row['category']} body style")
    if row["fuel_type"] == target["fuel_type"]:
        reasons.append(f"same {row['fuel_type'].lower()} powertrain")
    if abs(float(row["price_usd"]) - float(target["price_usd"])) <= float(target["price_usd"]) * 0.08:
        reasons.append("within 8% on price")
    if row["seating_capacity"] == target["seating_capacity"]:
        reasons.append(f"seats {int(row['seating_capacity'])}")
    if row["drive_type"] == target["drive_type"]:
        reasons.append(f"{row['drive_type']} drivetrain")
    if row["brand"] == target["brand"]:
        reasons.append("same brand loyalty")
    return ", ".join(reasons) if reasons else "closest available specification"


def _tradeoffs(target: pd.Series, row: pd.Series) -> str:
    """What the customer gives up — stated honestly, not buried."""
    gaps = []
    delta = float(row["price_usd"]) - float(target["price_usd"])
    if abs(delta) > float(target["price_usd"]) * 0.08:
        gaps.append(f"{'+' if delta > 0 else '-'}${abs(delta):,.0f} on price")
    if row["category"] != target["category"]:
        gaps.append(f"{row['category']} instead of {target['category']}")
    if row["fuel_type"] != target["fuel_type"]:
        gaps.append(f"{row['fuel_type']} instead of {target['fuel_type']}")
    if row["seating_capacity"] != target["seating_capacity"]:
        gaps.append(f"seats {int(row['seating_capacity'])} vs {int(target['seating_capacity'])}")
    if row["drive_type"] != target["drive_type"]:
        gaps.append(f"{row['drive_type']} vs {target['drive_type']}")
    return ", ".join(gaps) if gaps else "no material trade-off"
