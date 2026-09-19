"""
Locale-aware presentation of numbers, money, percentages and dates.

Output depends on the request's language (en/de separators and month names) and the tenant's
currency profile, both taken from `request_context`. Pure functions of that scope: no web-framework
imports, so backend services can use them to build user-facing text.
"""
from __future__ import annotations

from backend.core.request_context import current_language, current_profile

_DE_MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
              "August", "September", "Oktober", "November", "Dezember"]
_DE_MONTHS_SHORT = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul",
                    "Aug", "Sep", "Okt", "Nov", "Dez"]
_DE_DAYS = {"Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch",
            "Thursday": "Donnerstag", "Friday": "Freitag",
            "Saturday": "Samstag", "Sunday": "Sonntag"}


def is_de() -> bool:
    return current_language() == "de"


def _de_num(value: float, digits: int = 0) -> str:
    """Format with German separators: 1.234.567,89"""
    s = f"{value:,.{digits}f}"
    # en -> de: swap ',' and '.' via a placeholder so neither pass clobbers the other
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_num(value, digits: int = 0) -> str:
    """Plain number in the active language's separator convention."""
    if value is None:
        return "–" if is_de() else "n/a"
    value = float(value)
    return _de_num(value, digits) if is_de() else f"{value:,.{digits}f}"


def cur() -> str:
    """Currency display token for the active tenant ('$', '€', 'AED', ...)."""
    profile = current_profile()
    return profile.currency_symbol if profile else "€"


def cur_code() -> str:
    profile = current_profile()
    return profile.currency if profile else "EUR"


def _symbol_after() -> bool:
    profile = current_profile()
    position = profile.symbol_position if profile else None
    return (position == "suffix") if position else is_de()


def wrap_money(num: str) -> str:
    """Put the tenant's currency symbol on the correct side of an already-formatted number."""
    sym = cur()
    if _symbol_after():
        return f"{num} {sym}"
    return f"{sym} {num}" if sym.isalpha() else f"{sym}{num}"


def fmt_money(value, compact: bool = True) -> str:
    """
    Currency in the tenant's symbol and the active language's number convention.
      EN compact: €3.04B / AED 742.0M / $940K      EN exact: $1,234,567
      DE compact: 3,04 Mrd. € / 742,0 Mio. € / 940 Tsd. €   DE exact: 1.234.567 €
    """
    value = float(value or 0)
    a = abs(value)

    if is_de():
        if compact and a >= 1_000_000_000:
            return wrap_money(f"{_de_num(value / 1_000_000_000, 2)} Mrd.")
        if compact and a >= 1_000_000:
            return wrap_money(f"{_de_num(value / 1_000_000, 1)} Mio.")
        if compact and a >= 1_000:
            return wrap_money(f"{_de_num(value / 1_000, 0)} Tsd.")
        return wrap_money(_de_num(value, 0))

    if compact and a >= 1_000_000_000:
        return wrap_money(f"{value / 1_000_000_000:.2f}B")
    if compact and a >= 1_000_000:
        return wrap_money(f"{value / 1_000_000:.1f}M")
    if compact and a >= 1_000:
        return wrap_money(f"{value / 1_000:.0f}K")
    return wrap_money(f"{value:,.0f}")


def fmt_pct(value, digits: int = 1, signed: bool = False) -> str:
    """Percent in the active language. German uses a comma and a space before the sign: 12,4 % vs 12.4%."""
    if value is None:
        return "–" if is_de() else "n/a"
    value = float(value)
    body = _de_num(abs(value), digits) if is_de() else f"{abs(value):.{digits}f}"
    unit = " %" if is_de() else "%"
    if signed:
        if value > 0:
            return f"+{body}{unit}"
        if value < 0:
            return f"−{body}{unit}"
    return f"{body}{unit}"


def fmt_date(d, style: str = "short") -> str:
    """Date in the active language. DE uses DD.MM.YYYY; EN uses the short month name."""
    if d is None:
        return "–" if is_de() else "n/a"
    try:
        if is_de():
            if style == "month":
                return f"{_DE_MONTHS_SHORT[d.month - 1]} {d.year}"
            if style == "monthlong":
                return f"{_DE_MONTHS[d.month - 1]} {d.year}"
            return f"{d.day:02d}.{d.month:02d}.{d.year}"
        if style in ("month", "monthlong"):
            return d.strftime("%b %Y" if style == "month" else "%B %Y")
        return d.strftime("%d %b %Y")
    except (AttributeError, IndexError, ValueError):
        return str(d)


def fmt_weekday(name: str) -> str:
    """Translate an English weekday name as stored in Sale.day_of_week."""
    return _DE_DAYS.get(name, name) if is_de() else name
