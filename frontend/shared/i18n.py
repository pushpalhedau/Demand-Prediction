"""
German / English localisation for the PredictaX dashboard.

WHY THIS EXISTS
    The app ships for a German dealer group but is reviewed by an
    English-speaking team, so every screen has to render in either language
    from the same data. Streamlit re-runs the whole script on every
    interaction, so there is no "translate once at startup" step — each label
    is resolved at render time through `t()`.

THE ONE RULE THAT MATTERS
    Canonical values in the database are ENGLISH ("Estate", "Petrol",
    "Private"). Translation happens ONLY at the render boundary — the last
    step before st.dataframe / px.bar / st.metric.

    NEVER translate before a filter, a groupby, a merge or a comparison. A
    German label will not match an English value, the filter silently returns
    nothing, and the chart goes blank with no error to tell you why. Use
    `tv()` on a copy of the column you are about to display, not on the frame
    you are about to aggregate.

CACHING
    @st.cache_data functions must return RAW data, never formatted strings.
    A cached German string would be served to an English session (and vice
    versa) because the language is not part of the cache key. Format
    downstream of the cache, always.
"""

from __future__ import annotations

import streamlit as st

from backend.core.formatting import (  # noqa: F401  (re-exported: screens import formatting from here)
    cur, cur_code, fmt_date, fmt_money, fmt_num, fmt_pct, fmt_weekday, is_de, wrap_money,
)
from backend.core.request_context import current_profile, set_language

# Default language. German, because the primary audience is the dealer group;
# English is the toggle-away.
DEFAULT_LANG = "de"
LANGUAGES = {"de": "Deutsch", "en": "English"}

_MISSING: set[tuple[str, str]] = set()


# ─────────────────────────────────────────────────────────────────────────────
# Language state
# ─────────────────────────────────────────────────────────────────────────────

def get_lang() -> str:
    """Active language code. Falls back to the default outside a Streamlit run
    (scripts, tests, the seeders) so nothing here can raise."""
    lang = DEFAULT_LANG
    try:
        chosen = st.session_state.get("lang")
        if chosen in LANGUAGES:
            lang = chosen
        else:
            # ?lang=de in the URL pre-sets the language so a link can open in it.
            qp = st.query_params.get("lang")
            if qp in LANGUAGES:
                st.session_state["lang"] = qp
                lang = qp
    except Exception:  # noqa: BLE001 - outside a Streamlit run (scripts, tests) fall back to the default
        pass
    set_language(lang)
    return lang


def set_lang(lang: str) -> None:
    if lang in LANGUAGES:
        st.session_state["lang"] = lang


# ─────────────────────────────────────────────────────────────────────────────
# Number, currency and date formatting
#
# German convention inverts the separators and puts the symbol AFTER the
# number: 1.234.567,89 € against English €1,234,567.89.
# ─────────────────────────────────────────────────────────────────────────────

def plotly_number_format() -> dict:
    """d3-format separators for Plotly axes and hover labels. German charts
    need '.,' (thousands '.', decimal ',')."""
    if is_de():
        return {"separators": ",."}
    return {"separators": ".,"}


def hover_money(expr: str = "%{y:,.0f}") -> str:
    """
    Currency inside a Plotly hovertemplate.

    Plotly formats the number itself (using layout.separators from
    plotly_number_format), so all this does is put the symbol on the correct
    side for the tenant's currency.
    """
    return wrap_money(expr)


def hover_month(axis: str = "x") -> str:
    """
    Month-year inside a Plotly hovertemplate.

    Plotly's d3 time format has no German month names available without
    registering a locale, so German uses the unambiguous numeric MM.YYYY
    rather than printing English abbreviations on a German chart.
    """
    return "%{" + axis + "|%m.%Y}" if is_de() else "%{" + axis + "|%b %Y}"


# ─────────────────────────────────────────────────────────────────────────────
# Database VALUE translation
#
# These are the canonical English values stored in the DB. Translate for
# DISPLAY ONLY — see the module docstring.
# ─────────────────────────────────────────────────────────────────────────────

VALUE_MAP: dict[str, str] = {
    # Vehicle category
    "SUV": "SUV",
    "Compact": "Kompaktklasse",
    "Estate": "Kombi",
    "Sedan": "Limousine",
    "Small Car": "Kleinwagen",
    "Van": "Van",
    "Luxury": "Oberklasse",
    "Coupe": "Coupé",
    # Fuel type
    "Petrol": "Benzin",
    "Diesel": "Diesel",
    "Hybrid": "Hybrid",
    "Plug-in Hybrid": "Plug-in-Hybrid",
    "Electric": "Elektro",
    # Transmission
    "Manual": "Schaltgetriebe",
    "Automatic": "Automatik",
    "DSG": "DSG",
    "Single-Speed": "1-Gang",
    # Drive type
    "FWD": "Frontantrieb",
    "RWD": "Heckantrieb",
    "AWD": "Allradantrieb",
    # Customer type
    "Private": "Privat",
    "Commercial": "Gewerblich",
    # Financing
    "Cash": "Barzahlung",
    "Bank Loan": "Bankdarlehen",
    "Dealer Financing": "Händlerfinanzierung",
    "Balloon Financing": "Schlussratenfinanzierung",
    "Lease": "Leasing",
    # Occupation
    "Salaried Employee": "Angestellte:r",
    "Civil Servant": "Beamt:in",
    "Self-Employed": "Selbstständig",
    "Freelancer": "Freiberuflich",
    "Business Owner": "Unternehmer:in",
    "Skilled Worker": "Facharbeiter:in",
    "Public Sector": "Öffentlicher Dienst",
    "Retired": "Rentner:in",
    # Marketing channel / lead source
    "Online Ad": "Online-Anzeige",
    "Referral": "Empfehlung",
    "Showroom Walk-in": "Laufkundschaft",
    "Dealer Walk-in": "Laufkundschaft",
    "Search Engine": "Suchmaschine",
    "Social Media": "Social Media",
    "Marketplace Portal": "Fahrzeugbörse",
    "TV/Radio": "TV/Radio",
    # Season period
    "Year-End Registration Push": "Jahresend-Zulassungen",
    "Quarter-End Push": "Quartalsende",
    "Easter Campaign": "Osteraktion",
    "Summer Holidays": "Sommerferien",
    "IAA Mobility": "IAA Mobility",
    "New Year": "Jahresbeginn",
    # Dealer tier
    "Platinum": "Platin",
    "Gold": "Gold",
    "Silver": "Silber",
    # Vehicle origin
    "Domestic": "Inlandsproduktion",
    "Import": "Import",
    # Gender
    "Male": "Männlich",
    "Female": "Weiblich",
    "Other": "Divers",
    # Misc
    "Unclassified": "Nicht klassifiziert",
    "Unknown": "Unbekannt",
    "None": "Keine",
    "All": "Alle",
    "up": "steigend",
    "down": "fallend",
    "neutral": "neutral",
    "low": "niedrig",
    "medium": "mittel",
    "high": "hoch",
}


SEGMENT_INLINE = {
    "en": {"SUV": "SUV", "Sedan": "sedan", "Estate": "estate", "Compact": "compact",
           "Small Car": "small car", "Van": "van", "Luxury": "luxury",
           "Coupe": "coupé", "EV": "BEV", "Commercial": "commercial",
           "All": "all segments"},
    "de": {"SUV": "SUV", "Sedan": "Limousine", "Estate": "Kombi",
           "Compact": "Kompaktklasse", "Small Car": "Kleinwagen", "Van": "Van",
           "Luxury": "Oberklasse", "Coupe": "Coupé", "EV": "BEV",
           "Commercial": "Gewerbe", "All": "alle Segmente"},
}


def tseg(value):
    """Segment name as it reads inside a sentence."""
    return SEGMENT_INLINE.get(get_lang(), SEGMENT_INLINE["en"]).get(value, value)


def tv(value):
    """
    Translate a single DATABASE VALUE for display.

    Safe on None and on anything not in the map (returns it unchanged), so a
    new category value renders as its English self rather than crashing.
    """
    if not is_de() or value is None:
        return value
    return VALUE_MAP.get(value, value)


def tv_series(series):
    """
    Translate a pandas Series of database values for display.

    Call this on the column you are about to SHOW, never on one you are about
    to group, filter or join on.
    """
    if not is_de():
        return series
    return series.map(lambda v: VALUE_MAP.get(v, v) if v is not None else v)


# ─────────────────────────────────────────────────────────────────────────────
# UI string catalog
#
# Keys are grouped by area: app.* chrome, filter.*, kpi.*, tab.*, col.* table
# headers, msg.* notices. Add both languages together — an English-only entry
# silently renders English in German mode.
# ─────────────────────────────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # ── App chrome ──────────────────────────────────────────────────────
        "app.title": "PredictaX",
        "app.subtitle": "Demand intelligence for the dealer group",
        "app.header": "Automobile Demand Intelligence Platform",
        "app.header_sub": "Enterprise decision support — demand forecasting & customer analytics",
        "app.language": "Language",
        "app.data_mode": "Data source",
        "app.data_mode.real": "Dealer group (live)",
        "app.data_mode.test": "Test dataset",
        "app.filters": "Filters",
        "app.reset_filters": "Reset filters",
        "app.export_csv": "Export CSV",
        "app.download": "Download",
        "app.updated": "Updated",

        # ── Filters ─────────────────────────────────────────────────────────
        "filter.state": "Region",
        "filter.city": "City",
        "filter.brand": "Brand",
        "filter.category": "Segment",
        "filter.fuel": "Fuel type",
        "filter.dealer": "Store",
        "filter.period": "Period",
        "filter.customer_type": "Customer type",
        "filter.all": "All",
        "filter.date_from": "From",
        "filter.date_to": "To",

        # ── Tabs ────────────────────────────────────────────────────────────
        "tab.overview": "Executive Overview",
        "tab.forecasting": "Demand Forecasting",
        "tab.inventory": "Inventory & Placement",
        "tab.customers": "Customer Intelligence",
        "tab.regional": "Store Performance",
        "tab.comparison": "Comparative Analytics",
        "tab.sentiment": "Market Sentiment",
        "tab.ai_insights": "AI Insights",
        "tab.upload": "Upload Data",

        # ── KPIs ────────────────────────────────────────────────────────────
        "kpi.total_revenue": "Total revenue",
        "kpi.units_sold": "Units sold",
        "kpi.avg_price": "Average transaction price",
        "kpi.gross_profit": "Estimated gross",
        "kpi.discount": "Average discount",
        "kpi.inventory_value": "Inventory at cost",
        "kpi.days_supply": "Days' supply",
        "kpi.aged_stock": "Aged stock",
        "kpi.stockouts": "Stockouts",
        "kpi.ecb_rate": "Policy rate",
        "kpi.fuel_price": "Super E10",
        "kpi.conversion": "Test-drive conversion",
        "kpi.lead_time": "Lead-to-close",
        "kpi.active_customers": "Active customers",
        "kpi.commercial_share": "Commercial share",
        "kpi.ev_share": "BEV share",
        "kpi.vs_last_year": "vs last year",
        "kpi.per_month": "per month",
        "kpi.per_unit": "per unit",

        # ── Table columns ───────────────────────────────────────────────────
        "col.dealer": "Store",
        "col.state": "Region",
        "col.city": "City",
        "col.brand": "Brand",
        "col.model": "Model",
        "col.variant": "Trim",
        "col.category": "Segment",
        "col.fuel": "Fuel",
        "col.units": "Units",
        "col.revenue": "Revenue",
        "col.gross": "Est. gross",
        "col.stock": "Stock",
        "col.days_supply": "Days' supply",
        "col.capital": "Capital",
        "col.monthly_burn": "Monthly carry",
        "col.price": "List price",
        "col.discount": "Discount",
        "col.consumption": "Consumption",
        "col.co2": "CO₂",
        "col.vehicle_tax": "Annual vehicle tax",
        "col.range": "WLTP range",
        "col.power": "Power",
        "col.customer_type": "Customer type",
        "col.share": "Share",
        "col.yoy": "YoY",

        # ── Units ───────────────────────────────────────────────────────────
        "unit.l_100km": "l/100 km",
        "unit.kwh_100km": "kWh/100 km",
        "unit.co2": "g CO₂/km",
        "unit.km": "km",
        "unit.kw": "kW",
        "unit.units": "units",
        "unit.days": "days",
        "unit.sqm": "m²",

        # ── Messages ────────────────────────────────────────────────────────
        "msg.no_data": "No data for the selected filters.",
        "msg.loading": "Loading…",
        "msg.mock_data": "Showing mock data — no live API key configured.",
        "msg.gdpr": "Customer-level data is shown for authorised internal use only (GDPR Art. 6(1)(f)).",
        "msg.select_store": "Select a store",

        # ── Executive Overview ──────────────────────────────────────────────
        "ov.title": "Executive Overview",
        "ov.tab_glance": "Overview",
        "ov.tab_recs": "Recommendations",
        "ov.kpi.units": "Vehicles sold",
        "ov.kpi.revenue": "Total revenue",
        "ov.kpi.attainment": "Target attainment (TTM)",
        "ov.kpi.attainment_sub": "{actual} of {target} units",
        "ov.kpi.no_targets": "no targets set",
        "ov.kpi.penetration": "Finance & lease penetration",
        "ov.trend.title": "Revenue & unit trend",
        "ov.trend.caption": "Last 3 years of booked revenue and units, plus a 6-month projection (dashed / faded).",
        "ov.trend.units": "Units",
        "ov.trend.revenue": "Revenue",
        "ov.trend.revenue_proj": "Revenue (projected)",
        "ov.trend.projection": "projection",
        "ov.mix.category": "Sales mix by segment",
        "ov.mix.fuel": "Fuel type mix",
        "ov.store.title": "Sales by store",
        "ov.store.caption": "Top 5 rooftops by units; dashed line is the group average.",
        "ov.store.group_avg": "group avg {v}",
        "ov.rec.landing": "Where the year ends up",
        "ov.rec.landing_pct": "{v}% of plan",
        "ov.rec.landing_delta": "{sign}{units} units · {money} in profit",
        "ov.rec.value_total": "Total value in the actions below",
        "ov.rec.value_sub": "across {n} actions",
        "ov.rec.extra_needed": "Extra sales needed",
        "ov.rec.extra_none": "None",
        "ov.rec.on_track": "on track to hit plan",
        "ov.rec.extra_val": "+{v} cars",
        "ov.rec.extra_sub": "per store, each month",
        "ov.rec.next.title": "What to do next",
        "ov.rec.next.caption": "Plain-language actions, ranked by the estimated value of acting on each.",
        "ov.rec.none": "Nothing to flag for this selection — the group is on track to plan, with no stock, discounting or sales-pace problems standing out.",
        "ov.rec.chart.title": "Where the year lands",
        "ov.rec.chart.caption": "Monthly sales so far, and where the current pace takes the group by year-end.",
        "ov.rec.chart.actual": "Actual",
        "ov.rec.chart.projected": "Projected",
        "ov.rec.chart.plan_pace": "plan pace · {v}/mo",
        "ov.rec.chart.yaxis": "Units / month",
        "ov.rec.confidence": "{level} confidence",
        "ov.rec.est_value": "estimated value if acted on",
        "ov.rec.unavailable": "Decision brief unavailable for this scope ({e}).",
        "ov.err.render": "Error rendering Executive Overview: {e}",
        "conf.High": "High",
        "conf.Medium": "Medium",
        "conf.Low": "Low",
        "val.na": "N/A",
        "val.units": "{v} units",
        "val.yoy_pct": "{v}% YoY",
        "val.yoy_pts": "{v} pts YoY",

        # ── Sentiment Analysis ──────────────────────────────────────────────
        "sa.title": "Market Sentiment",
        "sa.window": "News window",
        "sa.refresh": "Refresh news",
        "sa.fetching": "Fetching the latest local auto news and scoring signals…",
        "sa.empty": "No recent signals yet.<br>Click <b>Refresh news</b> above to pull the latest local auto headlines and score them for the group's demand.",
        "sa.tab_watch": "Demand Watch",
        "sa.tab_fc": "Does news improve our forecast?",
        "sa.headline.label": "Expected demand impact · next ~30 days",
        "sa.headline.units": "about {v} units vs a normal month",
        "sa.gauge.scale": "headwind · flat · tailwind",
        "sa.word.tailwind": "Tailwind",
        "sa.word.headwind": "Headwind",
        "sa.word.flat": "Roughly flat",
        "sa.bottom_line": "Bottom line",
        "sa.bl.none": "No single story is moving the group's demand right now — the news nets out <b>roughly neutral</b> over the next ~30 days. Nothing here calls for a change to stocking or pricing; run the standard demand forecast and keep scanning the feed for an ECB rate move, a Kfz-Steuer or Dienstwagen change, or a fuel-price swing that would.",
        "sa.bl.mixed": "The news is <b>mixed and nets out roughly flat</b> over the next ~30 days — {up_n} supportive signal(s) ({up_theme}) roughly offset {dn_n} headwind(s) ({dn_theme}). No net stocking or pricing call for the group; work the individual signals below on their own merits.",
        "sa.bl.net": "The news adds up to a mild <b>{word}</b> ({pct}{units}) for the group's showroom demand over the next ~30 days.",
        "sa.bl.units_hint": ", roughly {v} units against a normal month",
        "sa.bl.driver": "The leading driver is <b>{label}</b>",
        "sa.bl.exposed": "Most exposed: ",
        "sa.bl.supportive_news": "supportive news",
        "sa.bl.headwind_news": "headwind news",
        "sa.bl.week": "This week:",
        "sa.bl.week_down": "protect days'-supply on {seg}, keep the desk leading with monthly-payment and residual talk-tracks, and be ready to pull incentive spend forward if showroom traffic softens.",
        "sa.bl.week_up": "keep {seg} stock full at the higher-volume Standorte and hold margin — you shouldn't need extra discount while this holds.",
        "sa.bl.seg_affected": "the affected segments",
        "sa.bl.seg_favour": "the segments in favour",
        "sa.drivers.title": "What's driving the signal",
        "sa.segment.title": "By segment",
        "sa.segment.caption": "News-driven demand change per vehicle segment. The headline weights these by the group's own sales mix.",
        "sa.latest.title": "Latest headlines scanned",
        "sa.latest.caption": "None carry a clear demand read this window — shown so you can see what's in the feed.",
        "sa.signals.title": "Signals to work",
        "sa.read.title": "This week's read for the group",
        "sa.read.button": "Generate read",
        "sa.read.spinner": "Reading every module and writing the briefing…",
        "sa.card.untitled": "Untitled",
        "sa.card.exposure_all": "affects showroom traffic across the whole book",
        "sa.card.exposure_seg": "lands on the group's {seg} demand",
        "sa.fc.title": "Does watching the news actually improve our forecast?",
        "sa.fc.unavailable": "Forecast engine unavailable: {e}",
        "sa.fc.horizon": "Look ahead",
        "sa.fc.measure": "Measure",
        "sa.fc.units": "Units",
        "sa.fc.revenue": "Revenue",
        "sa.fc.run": "Run check",
        "sa.fc.training": "Training both models…",
        "sa.fc.prompt": "Click **Run check** to compare.",
        "sa.fc.base_failed": "Baseline forecast failed: {e}",
        "sa.fc.actual": "Actual",
        "sa.fc.standard": "Standard forecast",
        "sa.fc.news_aware": "News-aware forecast",
        "sa.fc.yaxis_units": "Units / month",
        "sa.fc.yaxis_revenue": "Revenue / month ({cur})",
        "sa.status.fetched": "Fetched **{n}** headlines from **{source}** ",
        "sa.status.warn": "Refresh finished with warnings: {msg}",
        # News themes
        "sa.theme.de_auto_demand": "New registrations & demand",
        "sa.theme.ev_market_de": "Electric mobility",
        "sa.theme.tax_policy": "Vehicle tax & levies",
        "sa.theme.fuel_prices": "Fuel & energy prices",
        "sa.theme.de_macro_economy": "Economy & central bank",
        "sa.theme.auto_industry_de": "Auto industry & production",
        "sa.theme.auto_financing": "Financing & leasing",
        "sa.theme.incentives_offers": "Discounts & campaigns",
        # What a theme is mostly about, for the exposure line
        "sa.exp.tax_policy": "reprices running cost across the whole book and shifts mix toward low-CO2 and BEV",
        "sa.exp.auto_financing": "moves financed demand across the whole book — the fastest-acting driver in a leasing market",
        "sa.exp.de_macro_economy": "feeds the Leasingrate and financed demand across the whole book",
        "sa.exp.fuel_prices": "shifts mix a little from large SUV toward Kompakt, Kombi and hybrid",
        "sa.exp.incentives_offers": "changes the discount backdrop the desk is working against",
        "sa.exp.ev_market_de": "affects the group's BEV demand (ID.3/ID.4, Enyaq, Tesla, MG cross-shop)",
        "sa.exp.auto_industry_de": "hits regional confidence and can tighten supply of specific nameplates",
    },
    "de": {
        # ── App chrome ──────────────────────────────────────────────────────
        "app.title": "PredictaX",
        "app.subtitle": "Nachfrage-Intelligenz für die Handelsgruppe",
        "app.header": "Plattform für Fahrzeug-Nachfrageanalyse",
        "app.header_sub": "Entscheidungsunterstützung — Nachfrageprognose & Kundenanalyse",
        "app.language": "Sprache",
        "app.data_mode": "Datenquelle",
        "app.data_mode.real": "Handelsgruppe (live)",
        "app.data_mode.test": "Testdatensatz",
        "app.filters": "Filter",
        "app.reset_filters": "Filter zurücksetzen",
        "app.export_csv": "CSV exportieren",
        "app.download": "Herunterladen",
        "app.updated": "Aktualisiert",

        # ── Filters ─────────────────────────────────────────────────────────
        "filter.state": "Bundesland",
        "filter.city": "Stadt",
        "filter.brand": "Marke",
        "filter.category": "Segment",
        "filter.fuel": "Kraftstoffart",
        "filter.dealer": "Standort",
        "filter.period": "Zeitraum",
        "filter.customer_type": "Kundenart",
        "filter.all": "Alle",
        "filter.date_from": "Von",
        "filter.date_to": "Bis",

        # ── Tabs ────────────────────────────────────────────────────────────
        "tab.overview": "Management-Überblick",
        "tab.forecasting": "Nachfrageprognose",
        "tab.inventory": "Bestand & Platzierung",
        "tab.customers": "Kundenanalyse",
        "tab.regional": "Standort-Performance",
        "tab.comparison": "Vergleichsanalyse",
        "tab.sentiment": "Marktstimmung",
        "tab.ai_insights": "KI-Erkenntnisse",
        "tab.upload": "Daten hochladen",

        # ── KPIs ────────────────────────────────────────────────────────────
        "kpi.total_revenue": "Gesamtumsatz",
        "kpi.units_sold": "Verkaufte Einheiten",
        "kpi.avg_price": "Durchschnittlicher Transaktionspreis",
        "kpi.gross_profit": "Geschätzter Rohertrag",
        "kpi.discount": "Durchschnittlicher Nachlass",
        "kpi.inventory_value": "Bestand zu Einkaufswert",
        "kpi.days_supply": "Reichweite Bestand",
        "kpi.aged_stock": "Standzeitbestand",
        "kpi.stockouts": "Fehlbestände",
        "kpi.ecb_rate": "EZB-Leitzins",
        "kpi.fuel_price": "Super E10",
        "kpi.conversion": "Probefahrt-Abschlussquote",
        "kpi.lead_time": "Zeit bis Abschluss",
        "kpi.active_customers": "Aktive Kunden",
        "kpi.commercial_share": "Gewerbeanteil",
        "kpi.ev_share": "BEV-Anteil",
        "kpi.vs_last_year": "ggü. Vorjahr",
        "kpi.per_month": "pro Monat",
        "kpi.per_unit": "pro Einheit",

        # ── Table columns ───────────────────────────────────────────────────
        "col.dealer": "Standort",
        "col.state": "Bundesland",
        "col.city": "Stadt",
        "col.brand": "Marke",
        "col.model": "Modell",
        "col.variant": "Ausstattung",
        "col.category": "Segment",
        "col.fuel": "Kraftstoff",
        "col.units": "Einheiten",
        "col.revenue": "Umsatz",
        "col.gross": "Rohertrag",
        "col.stock": "Bestand",
        "col.days_supply": "Reichweite",
        "col.capital": "Kapitalbindung",
        "col.monthly_burn": "Monatliche Kosten",
        "col.price": "Listenpreis",
        "col.discount": "Nachlass",
        "col.consumption": "Verbrauch",
        "col.co2": "CO₂",
        "col.vehicle_tax": "Kfz-Steuer p. a.",
        "col.range": "WLTP-Reichweite",
        "col.power": "Leistung",
        "col.customer_type": "Kundenart",
        "col.share": "Anteil",
        "col.yoy": "ggü. Vorjahr",

        # ── Units ───────────────────────────────────────────────────────────
        "unit.l_100km": "l/100 km",
        "unit.kwh_100km": "kWh/100 km",
        "unit.co2": "g CO₂/km",
        "unit.km": "km",
        "unit.kw": "kW",
        "unit.units": "Einheiten",
        "unit.days": "Tage",
        "unit.sqm": "m²",

        # ── Messages ────────────────────────────────────────────────────────
        "msg.no_data": "Keine Daten für die gewählten Filter.",
        "msg.loading": "Wird geladen …",
        "msg.mock_data": "Es werden Beispieldaten angezeigt – kein Live-API-Schlüssel hinterlegt.",
        "msg.gdpr": "Kundenbezogene Daten nur für autorisierte interne Nutzung (DSGVO Art. 6 Abs. 1 lit. f).",
        "msg.select_store": "Standort auswählen",

        # ── Management-Überblick ────────────────────────────────────────────
        "ov.title": "Management-Überblick",
        "ov.tab_glance": "Überblick",
        "ov.tab_recs": "Empfehlungen",
        "ov.kpi.units": "Verkaufte Fahrzeuge",
        "ov.kpi.revenue": "Gesamtumsatz",
        "ov.kpi.attainment": "Zielerreichung (letzte 12 Mon.)",
        "ov.kpi.attainment_sub": "{actual} von {target} Einheiten",
        "ov.kpi.no_targets": "keine Ziele hinterlegt",
        "ov.kpi.penetration": "Finanzierungs- & Leasingquote",
        "ov.trend.title": "Umsatz- & Absatzentwicklung",
        "ov.trend.caption": "Die letzten 3 Jahre gebuchter Umsatz und Einheiten, dazu eine 6-Monats-Prognose (gestrichelt / blass).",
        "ov.trend.units": "Einheiten",
        "ov.trend.revenue": "Umsatz",
        "ov.trend.revenue_proj": "Umsatz (Prognose)",
        "ov.trend.projection": "Prognose",
        "ov.mix.category": "Absatzmix nach Segment",
        "ov.mix.fuel": "Mix nach Kraftstoffart",
        "ov.store.title": "Absatz nach Standort",
        "ov.store.caption": "Top-5-Standorte nach Einheiten; die gestrichelte Linie ist der Gruppendurchschnitt.",
        "ov.store.group_avg": "Gruppenschnitt {v}",
        "ov.rec.landing": "So endet das Jahr",
        "ov.rec.landing_pct": "{v} % des Plans",
        "ov.rec.landing_delta": "{sign}{units} Einheiten · {money} Ertrag",
        "ov.rec.value_total": "Gesamtwert der Maßnahmen unten",
        "ov.rec.value_sub": "über {n} Maßnahmen",
        "ov.rec.extra_needed": "Zusätzlich nötige Verkäufe",
        "ov.rec.extra_none": "Keine",
        "ov.rec.on_track": "Plan wird voraussichtlich erreicht",
        "ov.rec.extra_val": "+{v} Fahrzeuge",
        "ov.rec.extra_sub": "pro Standort und Monat",
        "ov.rec.next.title": "Nächste Schritte",
        "ov.rec.next.caption": "Konkrete Maßnahmen, sortiert nach dem geschätzten Wert der Umsetzung.",
        "ov.rec.none": "Für diese Auswahl gibt es nichts anzumerken — die Gruppe liegt im Plan, ohne auffällige Bestands-, Nachlass- oder Absatzprobleme.",
        "ov.rec.chart.title": "Wo das Jahr landet",
        "ov.rec.chart.caption": "Bisheriger Monatsabsatz und wohin das aktuelle Tempo die Gruppe zum Jahresende führt.",
        "ov.rec.chart.actual": "Ist",
        "ov.rec.chart.projected": "Prognose",
        "ov.rec.chart.plan_pace": "Plantempo · {v}/Mon.",
        "ov.rec.chart.yaxis": "Einheiten / Monat",
        "ov.rec.confidence": "Konfidenz {level}",
        "ov.rec.est_value": "geschätzter Wert bei Umsetzung",
        "ov.rec.unavailable": "Entscheidungsbriefing für diesen Zuschnitt nicht verfügbar ({e}).",
        "ov.err.render": "Fehler beim Rendern des Management-Überblicks: {e}",
        "conf.High": "hoch",
        "conf.Medium": "mittel",
        "conf.Low": "niedrig",
        "val.na": "k. A.",
        "val.units": "{v} Einheiten",
        "val.yoy_pct": "{v} % ggü. Vorjahr",
        "val.yoy_pts": "{v} Pp. ggü. Vorjahr",

        # ── Marktstimmung ───────────────────────────────────────────────────
        "sa.title": "Marktstimmung",
        "sa.window": "Nachrichtenzeitraum",
        "sa.refresh": "Nachrichten aktualisieren",
        "sa.fetching": "Aktuelle deutsche Auto-Nachrichten werden geladen und bewertet …",
        "sa.empty": "Noch keine aktuellen Signale.<br>Oben auf <b>Nachrichten aktualisieren</b> klicken, um aktuelle deutsche Auto-Schlagzeilen zu laden und für die Nachfrage der Gruppe zu bewerten.",
        "sa.tab_watch": "Nachfrage-Monitor",
        "sa.tab_fc": "Verbessern Nachrichten unsere Prognose?",
        "sa.headline.label": "Erwarteter Nachfrageeffekt · nächste ~30 Tage",
        "sa.headline.units": "rund {v} Einheiten ggü. einem normalen Monat",
        "sa.gauge.scale": "Gegenwind · neutral · Rückenwind",
        "sa.word.tailwind": "Rückenwind",
        "sa.word.headwind": "Gegenwind",
        "sa.word.flat": "Weitgehend neutral",
        "sa.bottom_line": "Fazit",
        "sa.bl.none": "Derzeit bewegt keine einzelne Meldung die Nachfrage der Gruppe — die Nachrichtenlage ist über die nächsten ~30 Tage <b>weitgehend neutral</b>. Daraus ergibt sich kein Anlass, Bestand oder Preise anzupassen; die Standardprognose fahren und den Feed weiter auf eine EZB-Zinsentscheidung, eine Änderung bei Kfz-Steuer oder Dienstwagenbesteuerung oder einen Ausschlag bei den Spritpreisen beobachten.",
        "sa.bl.mixed": "Die Nachrichtenlage ist <b>gemischt und hebt sich weitgehend auf</b> über die nächsten ~30 Tage — {up_n} stützende Signale ({up_theme}) gleichen {dn_n} Belastungen ({dn_theme}) weitgehend aus. Für die Gruppe ergibt sich daraus keine Bestands- oder Preisentscheidung; die Einzelsignale unten jeweils für sich bewerten.",
        "sa.bl.net": "Die Nachrichtenlage ergibt insgesamt leichten <b>{word}</b> ({pct}{units}) für die Showroom-Nachfrage der Gruppe über die nächsten ~30 Tage.",
        "sa.bl.units_hint": ", rund {v} Einheiten ggü. einem normalen Monat",
        "sa.bl.driver": "Haupttreiber ist <b>{label}</b>",
        "sa.bl.exposed": "Am stärksten betroffen: ",
        "sa.bl.supportive_news": "stützende Meldungen",
        "sa.bl.headwind_news": "belastende Meldungen",
        "sa.bl.week": "Diese Woche:",
        "sa.bl.week_down": "die Bestandsreichweite bei {seg} schützen, im Verkaufsgespräch weiter über Monatsrate und Restwert führen und bereit sein, Nachlässe vorzuziehen, falls die Frequenz nachlässt.",
        "sa.bl.week_up": "den Bestand bei {seg} an den absatzstarken Standorten voll halten und die Marge halten — zusätzlicher Nachlass sollte hier nicht nötig sein.",
        "sa.bl.seg_affected": "die betroffenen Segmente",
        "sa.bl.seg_favour": "die begünstigten Segmente",
        "sa.drivers.title": "Was das Signal treibt",
        "sa.segment.title": "Nach Segment",
        "sa.segment.caption": "Nachrichtengetriebene Nachfrageveränderung je Fahrzeugsegment. Der Headline-Wert gewichtet diese mit dem Absatzmix der Gruppe.",
        "sa.latest.title": "Zuletzt gescannte Schlagzeilen",
        "sa.latest.caption": "In diesem Zeitraum lässt keine eine klare Nachfragerichtung erkennen — hier zur Einsicht in den Feed.",
        "sa.signals.title": "Signale zum Bearbeiten",
        "sa.read.title": "Die Wochenlage für die Gruppe",
        "sa.read.button": "Lagebericht erstellen",
        "sa.read.spinner": "Alle Module werden ausgewertet und der Lagebericht geschrieben …",
        "sa.card.untitled": "Ohne Titel",
        "sa.card.exposure_all": "wirkt auf die Frequenz über das gesamte Geschäft",
        "sa.card.exposure_seg": "trifft die {seg}-Nachfrage der Gruppe",
        "sa.fc.title": "Verbessert die Nachrichtenauswertung unsere Prognose tatsächlich?",
        "sa.fc.unavailable": "Prognose-Engine nicht verfügbar: {e}",
        "sa.fc.horizon": "Prognosehorizont",
        "sa.fc.measure": "Kennzahl",
        "sa.fc.units": "Einheiten",
        "sa.fc.revenue": "Umsatz",
        "sa.fc.run": "Prüfung starten",
        "sa.fc.training": "Beide Modelle werden trainiert …",
        "sa.fc.prompt": "Auf **Prüfung starten** klicken, um zu vergleichen.",
        "sa.fc.base_failed": "Basisprognose fehlgeschlagen: {e}",
        "sa.fc.actual": "Ist",
        "sa.fc.standard": "Standardprognose",
        "sa.fc.news_aware": "Nachrichtengestützte Prognose",
        "sa.fc.yaxis_units": "Einheiten / Monat",
        "sa.fc.yaxis_revenue": "Umsatz / Monat ({cur})",
        "sa.status.fetched": "**{n}** Schlagzeilen von **{source}** geladen ",
        "sa.status.warn": "Aktualisierung mit Warnungen abgeschlossen: {msg}",
        # Nachrichtenthemen
        "sa.theme.de_auto_demand": "Neuzulassungen & Nachfrage",
        "sa.theme.ev_market_de": "Elektromobilität",
        "sa.theme.tax_policy": "Kfz-Steuer & Abgaben",
        "sa.theme.fuel_prices": "Kraftstoff- & Energiepreise",
        "sa.theme.de_macro_economy": "Konjunktur & EZB",
        "sa.theme.auto_industry_de": "Autoindustrie & Produktion",
        "sa.theme.auto_financing": "Finanzierung & Leasing",
        "sa.theme.incentives_offers": "Rabatte & Aktionen",
        # Worum es bei einem Thema im Kern geht, für die Expositionszeile
        "sa.exp.tax_policy": "verändert die Unterhaltskosten im gesamten Geschäft und verschiebt den Mix Richtung CO2-arm und BEV",
        "sa.exp.auto_financing": "bewegt die finanzierte Nachfrage im gesamten Geschäft — der schnellste Treiber in einem Leasingmarkt",
        "sa.exp.de_macro_economy": "wirkt auf die Leasingrate und die finanzierte Nachfrage im gesamten Geschäft",
        "sa.exp.fuel_prices": "verschiebt den Mix leicht von großen SUV Richtung Kompakt, Kombi und Hybrid",
        "sa.exp.incentives_offers": "verändert das Rabattumfeld, gegen das der Verkauf arbeitet",
        "sa.exp.ev_market_de": "betrifft die BEV-Nachfrage der Gruppe (ID.3/ID.4, Enyaq, Tesla, MG im Quervergleich)",
        "sa.exp.auto_industry_de": "trifft die regionale Stimmung und kann die Verfügbarkeit einzelner Modelle verknappen",
    },
}


def t(key: str, **kwargs) -> str:
    """
    Look up a UI string in the active language.

    Falls back to English, then to the key itself, so a translation added on
    one side only degrades to readable text instead of raising mid-render.
    Missing keys are recorded in `missing_keys()` for the translation sweep.
    """
    if key in ("filter.state", "col.state"):
        profile = current_profile()
        if profile and profile.region_label:
            return profile.region_label
    lang = get_lang()
    table = TRANSLATIONS.get(lang, {})
    if key in table:
        s = table[key]
    else:
        _MISSING.add((lang, key))
        s = TRANSLATIONS["en"].get(key, key)
    if kwargs:
        try:
            return s.format(**kwargs)
        except (KeyError, IndexError):
            return s
    return s


def missing_keys() -> list[tuple[str, str]]:
    """Every (lang, key) `t()` could not resolve this session — the to-do list
    for finishing a translation pass."""
    return sorted(_MISSING)


def language_selector(label_visibility: str = "visible") -> str:
    """Sidebar language toggle. Returns the active code."""
    codes = list(LANGUAGES)
    current = get_lang()
    choice = st.radio(
        t("app.language"),
        options=codes,
        index=codes.index(current),
        format_func=lambda c: LANGUAGES[c],
        horizontal=True,
        key="lang",
        label_visibility=label_visibility,
    )
    return choice
