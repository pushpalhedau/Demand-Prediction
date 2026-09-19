"""
Column-mapping engine: proposes, for one uploaded CSV, which source column feeds
each canonical field (and whether a unit conversion is needed).

Confidence levels, in the order they are tried:
  exact      the source name IS the canonical name (currency tokens ignored)
  converted  the source name implies a unit conversion (mpg, range_miles, horsepower...)
  alias      a known synonym (state/emirate -> region, zip_code -> postal_code...)
  fuzzy      a close spelling only. Never applied automatically; the wizard must confirm it.

A source column can feed at most one field. Columns with no home go to `extras`.
"""
import difflib
from dataclasses import dataclass, field

from backend.ingestion.catalog import TABLES, norm, strip_currency

FUZZY_CUTOFF = 0.86
AUTO_CONFIDENCE = ("exact", "converted", "alias")


@dataclass
class Choice:
    source: str
    transform: tuple = None      # ("mul", k) | ("inv", k) | None
    confidence: str = "exact"

    def to_json(self):
        return {"source": self.source, "transform": list(self.transform) if self.transform else None,
                "confidence": self.confidence}


@dataclass
class Proposal:
    table: str
    choices: dict = field(default_factory=dict)     # canonical field -> Choice
    unmapped: list = field(default_factory=list)    # source columns that will land in extras
    missing_required: list = field(default_factory=list)
    imperial_hint: bool = False                     # imperial-unit column names were matched

    def to_mapping(self, accept_fuzzy: bool = False, extras: bool = True) -> dict:
        cols = {f: c.to_json() for f, c in self.choices.items() if accept_fuzzy or c.confidence in AUTO_CONFIDENCE}
        return {"columns": cols, "extras": extras}


def _keys(name: str) -> tuple:
    n = norm(name)
    return n, strip_currency(n)


def propose_mapping(table: str, columns) -> Proposal:
    fields = TABLES[table]
    sources = {c: _keys(c) for c in columns}
    claimed_src, claimed_field = set(), set()
    proposal = Proposal(table)

    def take(f, src, transform, confidence):
        proposal.choices[f.name] = Choice(src, transform, confidence)
        claimed_src.add(src)
        claimed_field.add(f.name)

    def find(target_keys):
        # raw normalised match first, then currency-stripped
        for i in (0, 1):
            for src, ks in sources.items():
                if src not in claimed_src and ks[i] in target_keys[i]:
                    return src
        return None

    def keyset(name):
        n = norm(name)
        return ({n}, {strip_currency(n)})

    for f in fields:                                                    # 1. exact
        src = find(keyset(f.name))
        if src:
            take(f, src, None, "exact")

    for f in fields:                                                    # 2. unit-converted names
        if f.name in claimed_field:
            continue
        for alias, transform in f.converted:
            src = find(keyset(alias))
            if src:
                take(f, src, tuple(transform), "converted")
                break

    for f in fields:                                                    # 3. synonyms
        if f.name in claimed_field:
            continue
        for alias in f.aliases:
            src = find(keyset(alias))
            if src:
                take(f, src, None, "alias")
                break

    for f in fields:                                                    # 4. fuzzy (proposal only)
        if f.name in claimed_field:
            continue
        pool = {norm(s): s for s in sources if s not in claimed_src}
        targets = [norm(f.name)] + [norm(a) for a in f.aliases]
        best = None
        for t in targets:
            m = difflib.get_close_matches(t, list(pool), n=1, cutoff=FUZZY_CUTOFF)
            if m:
                best = pool[m[0]]
                break
        if best:
            take(f, best, None, "fuzzy")

    proposal.unmapped = [c for c in columns if c not in claimed_src]
    proposal.missing_required = [f.name for f in fields if f.required and f.name not in proposal.choices]
    proposal.imperial_hint = any(
        c.transform and alias_is_imperial(f, c) for f, c in proposal.choices.items())
    return proposal


# Whole words only: "mileage_kmpl" (km per litre) must not read as miles.
# Distance-bearing names only; sqft/gallon say nothing about km vs mi.
_IMPERIAL_WORDS = frozenset({"mpg", "mile", "miles", "mi"})


def alias_is_imperial(field_name: str, choice: Choice) -> bool:
    return bool(_IMPERIAL_WORDS & set(norm(choice.source).split("_")))
