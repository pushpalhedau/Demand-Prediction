import re

from backend.core.errors import InvalidSetting

from backend.db.rls import TENANT_CONFIG_KEYS

# A tenant admin can edit these, and some end up in HTML. Anything outside these shapes is rejected,
# not escaped: it keeps stored-XSS out of every place a value might later be rendered.
_RULES = {
    "currency": re.compile(r"^[A-Z]{3}$"),
    "currency_symbol": re.compile(r"^[^<>&\"'`\\\x00-\x1f]{1,4}$"),
    "symbol_position": re.compile(r"^(prefix|suffix)$"),
    "language": re.compile(r"^(en|de)$"),
    "region_label": re.compile(r"^[A-Za-z][A-Za-z \-]{0,29}$"),
    "country_name": re.compile(r"^[A-Za-z][A-Za-z .\-']{0,59}$"),
    "country": re.compile(r"^[A-Z]{2}$"),
    "news_hl": re.compile(r"^[a-z]{2}(-[A-Z]{2})?$"),
    "news_gl": re.compile(r"^[A-Z]{2}$"),
}


def validate_config(cfg: dict) -> dict:
    clean = {}
    for key, value in cfg.items():
        if key not in TENANT_CONFIG_KEYS or value in (None, ""):
            continue
        rule = _RULES.get(key)
        if rule is None or not isinstance(value, str) or not rule.match(value):
            raise InvalidSetting(f"Invalid value for {key.replace('_', ' ')}.")
        clean[key] = value
    return clean
