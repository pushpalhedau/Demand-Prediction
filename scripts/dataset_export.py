"""
Turn a generator's DataFrame into the platform's ideal upload format.

Uses the platform's own mapping engine (backend.ingestion.mapping), so a column is renamed only when the importer
would accept it with "exact", "alias" or "converted" confidence; converted columns are converted here (so the file is
metric and needs no unit choices on upload); fuzzy guesses and columns with no canonical home are dropped. Output has
the catalog's column order and clean types (whole numbers as integers, ISO dates, True/False).
"""
from __future__ import annotations

import pandas as pd

from backend.ingestion.catalog import TABLES
from backend.ingestion.mapping import AUTO_CONFIDENCE, propose_mapping


def canonicalize(table: str, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    proposal = propose_mapping(table, list(df.columns))
    out, renamed, converted = {}, [], []
    for field, choice in proposal.choices.items():
        if choice.confidence not in AUTO_CONFIDENCE:
            continue
        series = pd.to_numeric(df[choice.source], errors="coerce") if choice.transform else df[choice.source]
        if choice.transform:
            op, k = choice.transform
            series = series * k if op == "mul" else k / series.where(series > 0)
            converted.append(f"{choice.source} -> {field} ({op} {k:g})")
        elif choice.source != field:
            renamed.append(f"{choice.source} -> {field}")
        out[field] = series

    ordered = [f for f in TABLES[table] if f.name in out and not f.derived]
    result = pd.DataFrame({f.name: _clean(out[f.name], f.kind, f.name) for f in ordered})
    dropped = [c for c in df.columns if c in proposal.unmapped or
               (c in {ch.source for ch in proposal.choices.values() if ch.confidence not in AUTO_CONFIDENCE})]
    return result, {"renamed": renamed, "converted": converted, "dropped": dropped,
                    "missing_required": proposal.missing_required}


def _clean(series: pd.Series, kind: str, name: str) -> pd.Series:
    if kind == "int":
        return pd.to_numeric(series, errors="coerce").round().astype("Int64")
    if kind == "float":
        return pd.to_numeric(series, errors="coerce").round(4)
    if kind == "bool":
        return series.astype("boolean")
    if kind == "date":
        return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")
    return series
