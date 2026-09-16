"""
Group Demand & Operations Briefing — the detailed cross-module read behind the
Sentiment Analysis tab's "Generate read" button.

`build_briefing_context(filters, sentiment_stats)` gathers a compact snapshot
from every dashboard module — Executive Overview, Demand Forecasting,
Comparative Analytics, Store Performance, Customer Intelligence, Inventory
Intelligence — using the existing `database.queries` layer, each block guarded
so one failure never kills the brief.

`generate_group_briefing(context)` turns that into a structured report:
  - LIVE  (XAI_API_KEY set and accepted): Grok writes it from the context.
  - MOCK  (default): a fully deterministic template that walks every module with
    triggers, insights, recommendations and a ranked priority-action list.
"""

import logging
from datetime import date

import pandas as pd

from database.connection import get_db_session
from database.models import Dealer
import database.queries as Q
from sentiment.analyzers.grok_analyzer import (
    is_live_mode, _build_grok_client, _GROK_MODEL,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _num(v, nd=0):
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return "n/a"


def _pct(v, nd=1):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "n/a"
    s = f"{abs(v):.{nd}f}%"
    return f"+{s}" if v > 0 else (f"-{s}" if v < 0 else s)


def _money(v):
    """Compact EUR for big totals, in the UI's active language.
      EN: EUR 2.96B / EUR 53.2M      DE: 2,96 Mrd. EUR / 53,2 Mio. EUR"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "n/a"
    from utils.i18n import fmt_money
    return fmt_money(v, compact=True)


def _eur(v):
    """Exact EUR for per-unit / small figures: EUR 1,296 / 1.296 EUR."""
    try:
        from utils.i18n import fmt_money
        return fmt_money(float(v), compact=False)
    except (TypeError, ValueError):
        return "n/a"


# Back-compat alias: this used to be _usd, then AED. Call sites still use it.
_usd = _eur


def _get(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return d if d is not None else default


# ─────────────────────────────────────────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────────────────────────────────────────

def build_briefing_context(filters: dict, sentiment_stats: dict = None,
                           sentiment_articles: list = None) -> dict:
    filters = filters or {}
    ctx = {
        "as_of": date.today().isoformat(),
        "window": {
            "start": str(filters.get("start_date") or ""),
            "end": str(filters.get("end_date") or ""),
        },
        "scope": {k: filters[k] for k in
                  ("region", "city", "brand", "vehicle_category", "fuel_type")
                  if filters.get(k)},
        "errors": [],
    }

    s = get_db_session()
    try:
        from sqlalchemy import func
        from database.queries import _apply_dealer_scope
        try:
            ctx["rooftops"] = int(
                _apply_dealer_scope(s.query(func.count(Dealer.dealer_id)), filters).scalar() or 0
            )
        except Exception as e:
            ctx["rooftops"] = 24
            ctx["errors"].append(f"rooftops: {e}")

        _executive(s, filters, ctx)
        _demand_outlook(s, filters, ctx, sentiment_stats)
        _comparative(s, filters, ctx)
        _store_performance(s, filters, ctx)
        _customer(s, filters, ctx)
        _inventory(s, filters, ctx)
        _sentiment(ctx, sentiment_stats, sentiment_articles)
    finally:
        s.close()

    return ctx


def _executive(s, filters, ctx):
    try:
        k = Q.get_executive_kpis(s, filters)
        ctx["executive"] = {
            "units": k.get("total_sales"),
            "units_yoy_pct": k.get("total_sales_delta"),
            "revenue": k.get("total_revenue"),
            "revenue_yoy_pct": k.get("total_revenue_delta"),
            "ttm_units": k.get("ttm_units"),
            "annual_target": k.get("annual_target"),
            "target_attainment_pct": k.get("target_attainment_pct"),
            "target_attainment_delta": k.get("target_attainment_delta"),
            "finance_lease_pct": k.get("finance_lease_penetration"),
            "finance_lease_delta": k.get("finance_lease_penetration_delta"),
            "avg_discount_pct": k.get("avg_discount"),
            "avg_discount_delta": k.get("avg_discount_delta"),
            "top_category": k.get("top_vehicle_category"),
            "total_customers": k.get("total_customers"),
        }
        try:
            cat = Q.get_sales_by_category(s, filters)
            if not cat.empty:
                tot = cat["sales"].sum()
                ctx["executive"]["category_mix"] = {
                    r["vehicle_category"]: round(100 * r["sales"] / tot, 1)
                    for _, r in cat.head(5).iterrows()
                }
        except Exception:
            pass
        try:
            tm = Q.get_top_models(s, filters, limit=5)
            ctx["executive"]["top_models"] = [
                f"{r['brand']} {r['model']} ({_num(r['units'])})" for _, r in tm.iterrows()
            ]
        except Exception:
            pass
    except Exception as e:
        ctx["errors"].append(f"executive: {e}")


def _demand_outlook(s, filters, ctx, sent):
    try:
        tr = Q.get_monthly_revenue_trend(s, filters)
        out = {}
        if not tr.empty and "sales" in tr:
            tr = tr.sort_values(["year", "month"])
            u = tr["sales"].astype(float)
            if len(u) >= 6:
                last3 = u.tail(3).mean()
                prior3 = u.iloc[-6:-3].mean()
                out["run_rate_units_mo"] = round(last3)
                out["run_rate_prior_mo"] = round(prior3)
                out["run_rate_delta_pct"] = round(
                    (last3 - prior3) / prior3 * 100, 1) if prior3 else None
            out["last_month_units"] = round(float(u.iloc[-1]))
        if sent:
            out["news_signal_pct"] = sent.get("net_demand_signal_pct")
            out["news_segment_changes"] = sent.get("segment_changes")
        ctx["demand_outlook"] = out
    except Exception as e:
        ctx["errors"].append(f"demand_outlook: {e}")


def _comparative(s, filters, ctx):
    c = {}
    try:
        d = Q.get_yoy_drivers(s, filters, "store")
        if not d.empty and "delta_units" in d:
            d = d.sort_values("delta_units", ascending=False)
            c["gainers"] = [
                f"{r['name']} ({_pct_signed_int(r['delta_units'])})"
                for _, r in d.head(3).iterrows() if r["delta_units"] > 0
            ]
            c["laggards"] = [
                f"{r['name']} ({_pct_signed_int(r['delta_units'])})"
                for _, r in d.tail(3).iloc[::-1].iterrows() if r["delta_units"] < 0
            ]
            c["stores_down"] = int((d["delta_units"] < 0).sum())
            c["stores_total"] = int(len(d))
    except Exception as e:
        ctx["errors"].append(f"comparative.drivers: {e}")

    try:
        from analytics import yoy_attribution as YA
        sm = YA.summary(s, filters, "units")
        if sm:
            c["total_yoy_pct"] = sm.get("total_yoy_pct")
            c["controllable_yoy_pct"] = sm.get("controllable_yoy_pct")
            sp = sm.get("spread") or {}
            if sp:
                c["execution_beat"] = f"{sp.get('n_beat')}/{sp.get('n_total')}"
                c["execution_best"] = f"{sp.get('best_name')} ({_pct(sp.get('best_pct'))})"
                c["execution_worst"] = f"{sp.get('worst_name')} ({_pct(sp.get('worst_pct'))})"
    except Exception as e:
        ctx["errors"].append(f"comparative.attribution: {e}")

    # No tariff / import-duty exposure section in this build — deliberately
    # scoped out. Vehicle.origin still splits Domestic vs Import, but it drives
    # logistics lead time only, not a duty view.

    ctx["comparative"] = c


def _pct_signed_int(v):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return "n/a"
    return f"+{v:,}" if v > 0 else f"{v:,}"


def _store_performance(s, filters, ctx):
    try:
        lb = Q.get_dealer_performance_leaderboard(s, filters)
        p = {}
        if not lb.empty:
            att = lb["attainment_pct"].dropna()
            p["stores_reporting"] = int(len(lb))
            p["below_90pct_target"] = int((att < 90).sum())
            p["avg_attainment_pct"] = round(float(att.mean()), 1) if len(att) else None
            if "yoy_units_pct" in lb:
                yoy = lb["yoy_units_pct"].dropna()
                p["stores_down_yoy"] = int((yoy < 0).sum())
            cr = lb["close_rate"].dropna()
            if len(cr):
                p["close_rate_group_pct"] = round(float(cr.mean()) * 100, 1)
                p["close_rate_range_pct"] = [
                    round(float(cr.min()) * 100, 1), round(float(cr.max()) * 100, 1)
                ]
            lb2 = lb.dropna(subset=["attainment_pct"]).sort_values("attainment_pct")
            if not lb2.empty:
                w = lb2.iloc[0]
                b = lb2.iloc[-1]
                p["needs_attention"] = (
                    f"{w['dealer_name']} — {_num(w['attainment_pct'], 0)}% of target, "
                    f"{_pct(w.get('yoy_units_pct'))} YoY"
                )
                p["carrying_group"] = (
                    f"{b['dealer_name']} — {_num(b['attainment_pct'], 0)}% of target, "
                    f"{_pct(b.get('yoy_units_pct'))} YoY"
                )
        ctx["store_performance"] = p
    except Exception as e:
        ctx["errors"].append(f"store_performance: {e}")


def _customer(s, filters, ctx):
    try:
        book = Q.get_customer_book(s, filters)
        c = {}
        if not book.empty:
            buyers = book[book["n_deals"] > 0]
            c["customers_on_file"] = int(len(book))
            c["lifetime_buyers"] = int(len(buyers))
            if len(buyers):
                c["repeat_rate_pct"] = round(
                    100 * float((buyers["n_deals"] >= 2).mean()), 1)
            rev = float(buyers["lifetime_revenue"].sum())
            repeat_rev = float(buyers.loc[buyers["n_deals"] >= 2, "lifetime_revenue"].sum())
            c["repeat_revenue_share_pct"] = round(100 * repeat_rev / rev, 1) if rev else None
            if "churn_risk_score" in book:
                c["churn_risk_flagged"] = int((book["churn_risk_score"].fillna(0) >= 0.6).sum())
            if "months_since_last_deal" in book:
                c["lapsed_24mo_plus"] = int(
                    (book["months_since_last_deal"] > 24).sum())
            if "customer_segment" in book:
                seg = (buyers.groupby("customer_segment")["lifetime_revenue"]
                       .agg(["count", "sum"]).sort_values("sum", ascending=False))
                if not seg.empty:
                    top = seg.index[0]
                    c["top_value_segment"] = (
                        f"{top} — {_num(seg.iloc[0]['count'])} customers, "
                        f"{_money(seg.iloc[0]['sum'])} lifetime"
                    )
        # due back in market — lease maturities in the next quarter
        try:
            lm = Q.get_lease_maturity_recapture(s, filters, days_ahead=90)
            c["lease_returns_next_90d"] = int(len(lm)) if lm is not None else 0
        except Exception:
            pass
        ctx["customer"] = c
    except Exception as e:
        ctx["errors"].append(f"customer: {e}")


def _inventory(s, filters, ctx):
    try:
        snap = Q.get_inventory_snapshot(s, filters)
        inv = {}
        if not snap.empty:
            stock = float(snap["current_stock"].sum())
            daily_demand = float(snap["demand_forecast_30d"].clip(lower=0).sum()) / 30.0
            inv["stock_units"] = round(stock)
            inv["network_days_supply"] = round(stock / daily_demand, 0) if daily_demand else None
            inv["stockout_risk_lines"] = int(snap.get("stockout_flag", pd.Series(dtype=bool)).sum())
            inv["overstock_lines"] = int(snap.get("overstock_flag", pd.Series(dtype=bool)).sum())
            inv["reorder_lines"] = int(snap.get("reorder_needed", pd.Series(dtype=bool)).sum())
            try:
                ab = Q.get_aging_buckets(snap)
                if not ab.empty:
                    old = ab[ab["bucket"].str.contains("90")]
                    if not old.empty:
                        inv["aging_90plus_units"] = int(old["units"].sum())
                        inv["aging_90plus_capital"] = round(float(old["capital_eur"].sum()))
            except Exception:
                pass
        try:
            lrp = Q.get_lease_return_pipeline(s, filters, months_ahead=3)
            if lrp is not None and not lrp.empty:
                inv["lease_returns_90d"] = int(len(lrp))
                inv["lease_returns_in_money"] = int(lrp["in_the_money"].sum())
                inv["lease_returns_equity"] = round(
                    float(lrp.loc[lrp["in_the_money"], "equity_eur"].sum()))
        except Exception:
            pass
        try:
            ti = Q.get_trade_in_activity(s, filters)
            if ti is not None and not ti.empty and "sale_date" in ti:
                ti["sale_date"] = pd.to_datetime(ti["sale_date"], errors="coerce")
                cut = ti["sale_date"].max() - pd.Timedelta(days=90)
                recent = ti[(ti["sale_date"] >= cut) & (ti["trade_in_flag"] == True)]
                inv["trade_ins_last_90d"] = int(len(recent))
                if len(recent):
                    inv["avg_true_concession_pct"] = round(
                        float(recent["true_concession_pct"].dropna().mean()), 1)
        except Exception:
            pass
        ctx["inventory"] = inv
    except Exception as e:
        ctx["errors"].append(f"inventory: {e}")


def _sentiment(ctx, sent, articles):
    if not sent:
        return
    sctx = {
        "net_demand_signal_pct": sent.get("net_demand_signal_pct"),
        "segment_changes": sent.get("segment_changes"),
        "dominant_direction": sent.get("dominant_direction"),
        "total_headlines": sent.get("total_articles"),
    }
    if articles:
        df = pd.DataFrame(articles)
        if "demand_change_pct" in df:
            df["demand_change_pct"] = pd.to_numeric(df["demand_change_pct"], errors="coerce")
            nn = df[df["demand_direction"].fillna("neutral") != "neutral"]
            sctx["signals_with_read"] = int(len(nn))
            top = nn.reindex(
                nn["demand_change_pct"].abs().sort_values(ascending=False).index
            ).head(4)
            sctx["top_signals"] = [
                f"{(r.get('title') or '')[:90]} ({_pct(r.get('demand_change_pct'))})"
                for _, r in top.iterrows()
            ]
    ctx["sentiment"] = sctx


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def _lang_directive() -> str:
    """Make the briefing come back in the UI's active language."""
    try:
        from utils.i18n import get_lang
        lang = get_lang()
    except Exception:
        lang = "de"
    if lang == "de":
        return ("\n\nOUTPUT LANGUAGE: Write the entire briefing in GERMAN, in the "
                "register a German Autohaus-Geschäftsführung would use. Keep the "
                "SECTION HEADINGS exactly as specified in English, because the UI "
                "parses them to split the briefing into blocks.")
    return "\n\nOUTPUT LANGUAGE: Write the entire briefing in ENGLISH."


_SYSTEM = """You advise the leadership of a German automobile dealer group — a single regional group of 24 Standorte across six Bundesländer (Nordrhein-Westfalen, Bayern, Baden-Württemberg, Hessen, Niedersachsen, Rheinland-Pfalz). Franchises are the German volume and premium marques plus European and Asian volume brands; segment mix is roughly SUV 33%, Kompaktklasse 22%, Kombi 18%, Kleinwagen 13%, Limousine 8%, Van 4%, Oberklasse 2%.

Structural facts you must reason with:
- Roughly two thirds of units go to COMMERCIAL buyers (gewerblich — fleet, Dienstwagen under the 1%-Regelung). Private retail is the minority.
- The book runs on Leasing and Schlussratenfinanzierung, so the monthly payment — and therefore the ECB rate and residual values — drives demand more than list price does.
- German front-end gross is thin; the back end (Finanzierung, Leasing, Versicherung, Anschlussgarantie) carries a large share of the deal.
- The Umweltbonus ended in December 2023, so BEV demand is now price- and residual-led with no subsidy support.
- Showrooms cannot sell on Sundays (Ladenschlussgesetz); the calendar peaks are the quarter-end registration pushes (March, June, September) and the December run-out.
- There is a domestic industry, so plant, IG Metall and supplier news is local demand and sentiment news.

You are given a data snapshot covering every part of the business — Executive Overview, Demand Forecasting, Comparative Analytics (vs last year), Store Performance, Customer Intelligence and Inventory Intelligence — plus the current news read.

Write a detailed operating briefing for the group's Standortleiter, the Finanzierungs-/Leasing desk and the Gebrauchtwagen desk. For EACH section below, give: (a) where the group stands (the numbers, in plain terms), (b) what's notable — triggers, risks and opportunities, (c) concrete recommendations. Then close with a single ranked "This week — priority actions" list (P1…P6), each naming who acts and on what. Be specific, use the numbers you're given, and do not invent figures that aren't in the snapshot.

Sections, in order:
1. HEADLINE READ
2. EXECUTIVE OVERVIEW
3. DEMAND OUTLOOK
4. COMPARATIVE — VS LAST YEAR
5. STORE PERFORMANCE
6. CUSTOMER INTELLIGENCE
7. INVENTORY INTELLIGENCE
8. THIS WEEK — PRIORITY ACTIONS

Plain text only. No markdown symbols."""


def generate_group_briefing(context: dict) -> str:
    if is_live_mode():
        try:
            client = _build_grok_client()
            payload = _context_as_text(context)
            resp = client.chat.completions.create(
                model=_GROK_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM + _lang_directive()},
                    {"role": "user", "content": f"DATA SNAPSHOT\n\n{payload}\n\nWrite the briefing."},
                ],
                temperature=0.4,
                max_tokens=4000,
            )
            txt = (resp.choices[0].message.content or "").strip()
            if txt:
                return txt
        except Exception as e:
            logger.warning("Grok group briefing failed: %s — using template", e)
    return _template_briefing(context)


def _context_as_text(ctx: dict) -> str:
    import json
    return json.dumps(ctx, default=str, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic template
# ─────────────────────────────────────────────────────────────────────────────

def _template_briefing(ctx: dict) -> str:
    ex = ctx.get("executive", {}) or {}
    do = ctx.get("demand_outlook", {}) or {}
    cp = ctx.get("comparative", {}) or {}
    sp = ctx.get("store_performance", {}) or {}
    cu = ctx.get("customer", {}) or {}
    iv = ctx.get("inventory", {}) or {}
    se = ctx.get("sentiment", {}) or {}
    roofs = ctx.get("rooftops", 24)

    L = []
    P = []  # priority actions collected as we go

    L.append("GROUP DEMAND & OPERATIONS BRIEFING")
    L.append("")

    # ── 1. HEADLINE ───────────────────────────────────────────────
    att = ex.get("target_attainment_pct")
    u_yoy = ex.get("units_yoy_pct")
    news = se.get("net_demand_signal_pct")
    hl = []
    if att is not None:
        hl.append(f"the group is at {_num(att, 0)}% of the network's own annual plan"
                  + (" — behind" if att < 97 else " — on/ahead of plan"))
    if u_yoy is not None:
        hl.append(f"units are running {_pct(u_yoy)} vs last year")
    if news is not None:
        w = "a headwind" if news < -0.5 else ("a tailwind" if news > 0.5 else "roughly neutral")
        hl.append(f"the news read for the next ~30 days is {w} ({_pct(news)})")
    L.append("1. HEADLINE READ")
    L.append("   " + ("; ".join(hl).capitalize() + "." if hl else "Snapshot below."))
    biggest_risk = _biggest_risk(ctx)
    biggest_opp = _biggest_opp(ctx)
    if biggest_risk:
        L.append(f"   Biggest risk this week: {biggest_risk}")
    if biggest_opp:
        L.append(f"   Biggest opportunity this week: {biggest_opp}")
    L.append("")

    # ── 2. EXECUTIVE OVERVIEW ─────────────────────────────────────
    L.append("2. EXECUTIVE OVERVIEW")
    L.append("   Where we stand:")
    L.append(f"     - Units: {_num(ex.get('units'))} ({_pct(ex.get('units_yoy_pct'))} YoY)  |  "
             f"Revenue: {_money(ex.get('revenue'))} ({_pct(ex.get('revenue_yoy_pct'))} YoY)")
    if att is not None:
        gap = (ex.get("annual_target") or 0) - (ex.get("ttm_units") or 0)
        L.append(f"     - Target attainment (TTM): {_num(att, 0)}% of plan "
                 f"({_num(ex.get('ttm_units'))} of {_num(ex.get('annual_target'))} units"
                 + (f", {_num(gap)} short" if gap > 0 else "") + ")")
    L.append(f"     - Finance & lease penetration: {_num(ex.get('finance_lease_pct'), 0)}% "
             f"({_pct(ex.get('finance_lease_delta'))} pts YoY)")
    if ex.get("avg_discount_pct") is not None:
        L.append(f"     - Avg discount: {_num(ex.get('avg_discount_pct'), 1)}% "
                 f"({_pct(ex.get('avg_discount_delta'))} pts YoY)")
    if ex.get("category_mix"):
        L.append("     - Segment mix: " + ", ".join(
            f"{k} {v}%" for k, v in ex["category_mix"].items()))
    if ex.get("top_models"):
        L.append("     - Top models: " + ", ".join(ex["top_models"][:5]))
    L.append("   Triggers & recommendations:")
    if att is not None and att < 95:
        L.append(f"     - Behind plan at {_num(att, 0)}%. Push the TTM gap through the strongest "
                 "rooftops and the top-3 models; don't spread the effort evenly.")
        P.append(("P?", f"Close the plan gap ({_num((ex.get('annual_target') or 0) - (ex.get('ttm_units') or 0))} units) — GMs, focus stock + floor traffic on the top-selling models."))
    elif att is not None:
        L.append(f"     - On plan at {_num(att, 0)}%. Protect gross — resist discounting into a market you're already winning.")
    if ex.get("finance_lease_delta") is not None and ex["finance_lease_delta"] < -1:
        L.append("     - F&I penetration is slipping YoY. Re-brief the desk on lender menus and "
                 "lease vs. finance positioning; every cash deal is lost F&I gross.")
        P.append(("P?", "F&I desk — rebuild the lender menu and lease presentation; penetration is down YoY."))
    if ex.get("avg_discount_delta") is not None and ex["avg_discount_delta"] > 0.5:
        L.append("     - Discounting is up YoY. Check it's buying incremental volume and not just "
                 "margin give-back on deals that would have closed anyway.")
    L.append("")

    # ── 3. DEMAND OUTLOOK ────────────────────────────────────────
    L.append("3. DEMAND OUTLOOK")
    if do.get("run_rate_units_mo"):
        L.append(f"     - Run-rate: {_num(do['run_rate_units_mo'])} units/mo (last 3 mo) vs "
                 f"{_num(do.get('run_rate_prior_mo'))} the 3 before ({_pct(do.get('run_rate_delta_pct'))})")
    if do.get("last_month_units"):
        L.append(f"     - Most recent full month: {_num(do['last_month_units'])} units")
    if do.get("news_signal_pct") is not None:
        L.append(f"     - News signal, next ~30 days: {_pct(do['news_signal_pct'])} "
                 "(sales-mix weighted)")
    seg = do.get("news_segment_changes") or {}
    seg = {k: v for k, v in seg.items() if k != "All" and abs(v or 0) >= 0.05}
    if seg:
        L.append("     - Segment reads from the news: " + ", ".join(
            f"{k} {_pct(v)}" for k, v in sorted(seg.items(), key=lambda x: -abs(x[1]))))
    L.append("   Triggers & recommendations:")
    if do.get("run_rate_delta_pct") is not None and do["run_rate_delta_pct"] < -3:
        L.append("     - Run-rate is cooling. Tighten orders on the slow segments now rather than "
                 "carrying the stock into aging.")
        P.append(("P?", "Ordering — trim the next order on the cooling segments; run-rate is down 3%+."))
    if seg:
        worst = min(seg.items(), key=lambda x: x[1])
        best = max(seg.items(), key=lambda x: x[1])
        if worst[1] < -0.3:
            L.append(f"     - {worst[0]} is the segment most exposed to the current news "
                     f"({_pct(worst[1])}). Watch its days'-supply and be ready with incentive or "
                     "trade support if traffic softens.")
        if best[1] > 0.3:
            L.append(f"     - {best[0]} has the supportive read ({_pct(best[1])}). Keep it stocked "
                     "at the higher-volume rooftops and hold margin.")
    if not do:
        L.append("     - Trend data unavailable for this scope.")
    L.append("")

    # ── 4. COMPARATIVE ──────────────────────────────────────────
    L.append("4. COMPARATIVE — VS LAST YEAR")
    if cp.get("total_yoy_pct") is not None:
        line = f"     - Group YoY: {_pct(cp['total_yoy_pct'])} units"
        if cp.get("controllable_yoy_pct") is not None:
            line += f"; of that, {_pct(cp['controllable_yoy_pct'])} is controllable execution " \
                    "(the rest is calendar/network effects)"
        L.append(line)
    if cp.get("stores_down") is not None:
        L.append(f"     - {cp['stores_down']} of {cp.get('stores_total', roofs)} stores are down vs last year")
    if cp.get("gainers"):
        L.append("     - Carrying the group: " + ", ".join(cp["gainers"]))
    if cp.get("laggards"):
        L.append("     - Dragging: " + ", ".join(cp["laggards"]))
    if cp.get("execution_worst"):
        L.append(f"     - Weakest execution vs the group's own rate: {cp['execution_worst']}; "
                 f"strongest: {cp.get('execution_best', 'n/a')}")
    L.append("   Triggers & recommendations:")
    if cp.get("laggards"):
        P.append(("P?", f"Store ops — sit down with {cp['laggards'][0].split(' (')[0]} (biggest YoY drag); "
                        "review stock, floor coverage and lead handling."))
        L.append(f"     - {cp['laggards'][0].split(' (')[0]} is the biggest single drag on the YoY "
                 "number. That's where a store visit pays back fastest.")
    L.append("")

    # ── 5. STORE PERFORMANCE ────────────────────────────────────
    L.append("5. STORE PERFORMANCE")
    if sp.get("below_90pct_target") is not None:
        L.append(f"     - {sp['below_90pct_target']} of {sp.get('stores_reporting', roofs)} "
                 f"rooftops are below 90% of their own target "
                 f"(group avg {_num(sp.get('avg_attainment_pct'), 0)}%)")
    if sp.get("stores_down_yoy") is not None:
        L.append(f"     - {sp['stores_down_yoy']} rooftops down YoY on trailing-12 units")
    if sp.get("carrying_group"):
        L.append(f"     - Carrying the group: {sp['carrying_group']}")
    if sp.get("needs_attention"):
        L.append(f"     - Needs attention: {sp['needs_attention']}")
    if sp.get("close_rate_group_pct") is not None:
        rng = sp.get("close_rate_range_pct") or []
        L.append(f"     - Showroom close rate: {_num(sp['close_rate_group_pct'], 0)}% group"
                 + (f", {_num(rng[0], 0)}–{_num(rng[1], 0)}% by store" if rng else ""))
    L.append("   Triggers & recommendations:")
    if sp.get("needs_attention"):
        store = sp["needs_attention"].split(" — ")[0]
        L.append(f"     - {store} is the lowest pace-to-target. Get a 30-day plan from that GM: "
                 "stock mix, appointment set/show rate, and used-to-new ratio.")
        P.append(("P?", f"{store} — GM to deliver a 30-day recovery plan (lowest pace vs target)."))
    if sp.get("close_rate_range_pct") and (sp["close_rate_range_pct"][1] - sp["close_rate_range_pct"][0]) > 15:
        L.append("     - Close-rate spread across stores is wide. Have the strongest closer walk "
                 "the weakest store's floor process for a day.")
    L.append("")

    # ── 6. CUSTOMER INTELLIGENCE ────────────────────────────────
    L.append("6. CUSTOMER INTELLIGENCE")
    if cu.get("customers_on_file") is not None:
        L.append(f"     - {_num(cu['customers_on_file'])} customers on file; "
                 f"{_num(cu.get('lifetime_buyers'))} have bought at least once")
    if cu.get("repeat_rate_pct") is not None:
        L.append(f"     - Repeat rate: {_num(cu['repeat_rate_pct'], 0)}% of buyers have 2+ deals; "
                 f"repeat business is {_num(cu.get('repeat_revenue_share_pct'), 0)}% of lifetime revenue")
    if cu.get("lease_returns_next_90d") is not None:
        L.append(f"     - Due back in market: {_num(cu['lease_returns_next_90d'])} lease maturities "
                 "in the next 90 days (known unit, known payoff, known month)")
    if cu.get("churn_risk_flagged") is not None:
        L.append(f"     - {_num(cu['churn_risk_flagged'])} customers flagged churn-risk; "
                 f"{_num(cu.get('lapsed_24mo_plus'))} prior buyers haven't returned in 24+ months")
    if cu.get("top_value_segment"):
        L.append(f"     - Highest-value segment: {cu['top_value_segment']}")
    L.append("   Triggers & recommendations:")
    if cu.get("lease_returns_next_90d"):
        L.append("     - Work the lease returns first — highest-intent list you have. Assign each "
                 "to the originating store's BDC with a payment-matched replacement quote.")
        P.append(("P?", f"BDC — outbound the {_num(cu['lease_returns_next_90d'])} lease returns due "
                        "this quarter with a payment-matched replacement offer."))
    if cu.get("churn_risk_flagged"):
        L.append("     - Put the churn-risk names on a service-first re-engagement track; a "
                 "service visit lifts repurchase odds materially.")
    L.append("")

    # ── 7. INVENTORY INTELLIGENCE ──────────────────────────────
    L.append("7. INVENTORY INTELLIGENCE")
    if iv.get("stock_units") is not None:
        L.append(f"     - Network stock: {_num(iv['stock_units'])} units, "
                 f"{_num(iv.get('network_days_supply'), 0)} days of supply")
    if iv.get("stockout_risk_lines") is not None:
        L.append(f"     - {iv['stockout_risk_lines']} lines at stockout risk, "
                 f"{iv.get('overstock_lines', 0)} overstocked, "
                 f"{iv.get('reorder_lines', 0)} flagged reorder")
    if iv.get("aging_90plus_units") is not None:
        L.append(f"     - Aging 90+ days: {_num(iv['aging_90plus_units'])} units, "
                 f"{_money(iv.get('aging_90plus_capital'))} tied up")
    if iv.get("lease_returns_90d") is not None:
        L.append(f"     - Lease returns over the next quarter: {_num(iv['lease_returns_90d'])} units, "
                 f"{iv.get('lease_returns_in_money', 0)} coming back in the money "
                 f"({_usd(iv.get('lease_returns_equity'))} of retained equity if kept, not auctioned)")
    if iv.get("trade_ins_last_90d") is not None:
        L.append(f"     - Trade-in intake (90d): {_num(iv['trade_ins_last_90d'])} units"
                 + (f", true concession {_num(iv.get('avg_true_concession_pct'), 1)}% of price"
                    if iv.get("avg_true_concession_pct") is not None else ""))
    L.append("   Triggers & recommendations:")
    if iv.get("network_days_supply") is not None and iv["network_days_supply"] < 45:
        L.append(f"     - Days of supply is thin ({_num(iv['network_days_supply'], 0)}). Expedite the "
                 "reorder lines on the fast movers before you lose sales to no-stock.")
        P.append(("P?", "Ordering — expedite the stockout-risk reorder lines; network days-supply under 45."))
    elif iv.get("network_days_supply") is not None and iv["network_days_supply"] > 85:
        L.append(f"     - Days of supply is heavy ({_num(iv['network_days_supply'], 0)}). Slow "
                 "incoming orders and move the overstock lines with a targeted spiff.")
        P.append(("P?", "Ordering — hold incoming orders and spiff the overstocked lines; days-supply over 85."))
    if iv.get("aging_90plus_units"):
        L.append(f"     - {_num(iv['aging_90plus_units'])} units past 90 days are burning holding "
                 "cost daily. Price-to-market this week and give the sales team a clear aged-unit spiff.")
        P.append(("P?", f"Used/new desk — reprice and spiff the {_num(iv['aging_90plus_units'])} units aged 90+ days."))
    if iv.get("lease_returns_in_money"):
        L.append(f"     - {iv['lease_returns_in_money']} lease returns are coming back in the money. "
                 "Pull them into inventory rather than grounding to auction.")
    L.append("")

    # ── 8. PRIORITY ACTIONS ────────────────────────────────────
    L.append("8. THIS WEEK — PRIORITY ACTIONS")
    if not P:
        L.append("   No red flags in the snapshot — hold the plan, protect gross, keep scanning "
                 "the news feed.")
    else:
        for i, (_, action) in enumerate(P[:6], 1):
            L.append(f"   P{i}. {action}")

    return "\n".join(L).rstrip()


def _biggest_risk(ctx):
    ex = ctx.get("executive", {}) or {}
    iv = ctx.get("inventory", {}) or {}
    sp = ctx.get("store_performance", {}) or {}
    se = ctx.get("sentiment", {}) or {}
    if ex.get("target_attainment_pct") is not None and ex["target_attainment_pct"] < 90:
        return f"the group is well behind plan ({_num(ex['target_attainment_pct'], 0)}% of target)"
    if iv.get("aging_90plus_units") and iv["aging_90plus_units"] > 50:
        return f"{_num(iv['aging_90plus_units'])} units aged 90+ days ({_money(iv.get('aging_90plus_capital'))} tied up)"
    if se.get("net_demand_signal_pct") is not None and se["net_demand_signal_pct"] < -1.0:
        return f"the news read is a real headwind ({_pct(se['net_demand_signal_pct'])})"
    if sp.get("below_90pct_target") and sp["below_90pct_target"] >= 6:
        return f"{sp['below_90pct_target']} rooftops below 90% of target"
    return None


def _biggest_opp(ctx):
    cu = ctx.get("customer", {}) or {}
    iv = ctx.get("inventory", {}) or {}
    do = ctx.get("demand_outlook", {}) or {}
    if cu.get("lease_returns_next_90d") and cu["lease_returns_next_90d"] > 20:
        return f"{_num(cu['lease_returns_next_90d'])} lease maturities in the next 90 days — the highest-intent list in the CRM"
    if iv.get("lease_returns_in_money") and iv["lease_returns_in_money"] > 10:
        return f"{iv['lease_returns_in_money']} in-the-money lease returns to retain rather than auction"
    seg = do.get("news_segment_changes") or {}
    up = [(k, v) for k, v in seg.items() if k != "All" and (v or 0) > 0.3]
    if up:
        k, v = max(up, key=lambda x: x[1])
        return f"the news supports {k} demand ({_pct(v)}) — keep it stocked and hold margin"
    return None
