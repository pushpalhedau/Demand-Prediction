"""
Transform (mapping, units, type coercion, derivations, validation) and load
(COPY -> temp table -> INSERT ... SELECT, all inside one tenant-scoped
transaction so row-level security checks every row and a failure loads nothing).
"""
import io
import json

import pandas as pd

from backend.core.errors import IngestError
from backend.core.request_context import tenant_context
from backend.db.connection import get_db_session
from backend.db.models import Customer, Dealer, ExternalFactor, Inventory, Sale, Vehicle
from backend.ingestion.catalog import LOAD_ORDER, MI_TO_KM, NATURAL_KEY, REQUIRED_TABLES, TABLES, field_map

MODELS = {"vehicles": Vehicle, "dealers": Dealer, "customers": Customer,
          "external_factors": ExternalFactor, "sales": Sale, "inventory": Inventory}

_TRUE = {"true", "t", "yes", "y", "1", "1.0", "x"}
_FALSE = {"false", "f", "no", "n", "0", "0.0"}


def read_csv(source) -> pd.DataFrame:
    return pd.read_csv(source, dtype=str, keep_default_na=False, na_values=[""], encoding_errors="replace")


# ── coercion ────────────────────────────────────────────────────────────────

def _to_numeric(s: pd.Series, decimal: str = ".") -> pd.Series:
    """decimal="," reads 1.234,56 as 1234.56. Guessing per value is unsafe: "12,5" could be either."""
    cleaned = s.astype("string").str.strip()
    if decimal == ",":
        cleaned = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        cleaned = cleaned.str.replace(",", "", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def _coerce(series: pd.Series, kind: str, dayfirst: bool, decimal: str = ".") -> pd.Series:
    s = series.astype("string").str.strip()
    s = s.mask(s == "")
    if kind == "str":
        return s
    if kind == "bool":
        low = s.str.lower()
        out = pd.Series(pd.NA, index=s.index, dtype="boolean")
        out = out.mask(low.isin(_TRUE), True).mask(low.isin(_FALSE), False)
        return out
    if kind == "date":
        parsed = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=dayfirst)
        return parsed.dt.strftime("%Y-%m-%d").astype("string")
    num = _to_numeric(s, decimal)
    return num.round().astype("Int64") if kind == "int" else num.astype("float64")


def _apply_transform(num: pd.Series, transform) -> pd.Series:
    if not transform:
        return num
    op, k = transform
    if op == "mul":
        return num * k
    if op == "inv":
        return k / num.where(num > 0)
    raise IngestError(f"unknown transform {op!r}")


def _slug(s: pd.Series) -> pd.Series:
    return s.astype("string").str.lower().str.replace(r"[^0-9a-z]+", "-", regex=True).str.strip("-")


# ── table transform ─────────────────────────────────────────────────────────

def transform_table(table: str, raw: pd.DataFrame, mapping: dict, units: dict = None,
                    dayfirst: bool = False, decimal: str = ".") -> tuple:
    """Return (canonical DataFrame, report). Raises IngestError on blocking problems."""
    units = units or {}
    fmap = field_map(table)
    cols = mapping.get("columns", {})
    report = {"table": table, "rows_in": int(len(raw)), "coercion_failures": {}, "warnings": []}

    for name in cols:
        if name not in fmap:
            raise IngestError(f"{table}: {name!r} is not a field of this table")
    for src in (c["source"] for c in cols.values()):
        if src not in raw.columns:
            raise IngestError(f"{table}: mapped column {src!r} is not in the uploaded file")

    out = pd.DataFrame(index=raw.index)
    for name, choice in cols.items():
        f = fmap[name]
        src = raw[choice["source"]]
        if f.kind in ("int", "float"):
            num = _apply_transform(_to_numeric(src, decimal), tuple(choice["transform"]) if choice.get("transform") else None)
            if f.dim == "distance" and units.get("distance") == "mi" and not choice.get("transform"):
                num = num * MI_TO_KM
            before = src.notna().sum()
            col = num.round().astype("Int64") if f.kind == "int" else num.astype("float64")
            failed = int(before - col.notna().sum())
        else:
            col = _coerce(src, f.kind, dayfirst, decimal)
            failed = int(src.notna().sum() - col.notna().sum())
        if failed > 0:
            report["coercion_failures"][name] = failed
        out[name] = col

    missing = [f.name for f in TABLES[table] if f.required and f.name not in out.columns]
    if missing:
        raise IngestError(f"{table}: required field(s) not mapped: {', '.join(missing)}")

    if "postal_code" in out:
        out["postal_code"] = out["postal_code"].str.replace(r"\.0$", "", regex=True)

    _derive(table, out, report)

    # defaults fill NULLs, but only in columns the customer actually supplied
    for name in list(out.columns):
        f = fmap.get(name)
        if f is None or f.default is None:
            continue
        if f.default == "median":
            med = out[name].median()
            if pd.notna(med):
                out[name] = out[name].fillna(round(med) if f.kind == "int" else med)
        else:
            out[name] = out[name].fillna(f.default)

    required = [f.name for f in TABLES[table] if f.required and not f.derived]
    keep = pd.Series(True, index=out.index)
    for name in required:
        keep &= out[name].notna()
    dropped = int((~keep).sum())
    if dropped:
        report["warnings"].append(f"{dropped:,} row(s) dropped: blank {', '.join(required)}")
    out = out[keep]

    key = [k for k in NATURAL_KEY[table] if k in out.columns]
    if key:
        dup = int(out.duplicated(subset=key, keep="last").sum())
        if dup:
            out = out.drop_duplicates(subset=key, keep="last")
            report["warnings"].append(f"{dup:,} duplicate row(s) ignored (same {'/'.join(key)})")

    if out.empty:
        raise IngestError(f"{table}: no usable rows after validation")

    if mapping.get("extras", True):
        extra_cols = [c for c in raw.columns if c not in {v["source"] for v in cols.values()}]
        report["extras_columns"] = extra_cols
        if extra_cols:
            sub = raw.loc[out.index, extra_cols]
            out["extras"] = [json.dumps({k: v for k, v in rec.items() if pd.notna(v)}) or None
                             for rec in sub.to_dict("records")]
            out["extras"] = out["extras"].mask(out["extras"] == "{}")

    report["rows_out"] = int(len(out))
    return out.reset_index(drop=True), report


def _derive(table: str, df: pd.DataFrame, report: dict) -> None:
    if table == "sales":
        _fill_ids(df, "sale_id", "S")
        if "units_sold" not in df:
            df["units_sold"] = 1
        df["units_sold"] = df["units_sold"].fillna(1)
        d = pd.to_datetime(df["sale_date"], errors="coerce")
        _fill(df, "year", d.dt.year.astype("Int64"))
        _fill(df, "month", d.dt.month.astype("Int64"))
        _fill(df, "quarter", ("Q" + d.dt.quarter.astype("Int64").astype("string")))
        _fill(df, "day_of_week", d.dt.day_name().astype("string"))
        if "dealer_id" not in df and "dealer_name" in df:
            df["dealer_id"] = _slug(df["dealer_name"])
        if "vehicle_id" not in df and {"brand", "model"} <= set(df.columns):
            parts = [df[c].fillna("") for c in ("brand", "model", "vehicle_category") if c in df]
            df["vehicle_id"] = _slug(parts[0].str.cat(parts[1:], sep="-"))
        def money(c):
            return df[c].fillna(0) if c in df else 0

        if "selling_price" not in df and "total_revenue_excl_tax" in df:
            df["selling_price"] = df["total_revenue_excl_tax"] / df["units_sold"].where(df["units_sold"] > 0)
        elif "selling_price" not in df and "total_revenue_incl_tax" in df:
            df["selling_price"] = (df["total_revenue_incl_tax"] - money("tax_amount")) / df["units_sold"].where(df["units_sold"] > 0)
        if "selling_price" not in df:
            raise IngestError("sales: needs a selling price or a total revenue column")
        sp = df["selling_price"]
        excl = sp * df["units_sold"] + money("accessories_revenue") + money("insurance_revenue") + money("extended_warranty")
        _fill(df, "total_revenue_excl_tax", excl.astype("float64"))
        _fill(df, "total_revenue_incl_tax", (df["total_revenue_excl_tax"] + money("tax_amount")).astype("float64"))
    elif table == "inventory":
        _fill_ids(df, "inventory_id", "I")
        if "current_stock" in df:
            _fill(df, "stockout_flag", (df["current_stock"] == 0).astype("boolean"))
    elif table == "external_factors":
        d = pd.to_datetime(df["date"], errors="coerce")
        _fill(df, "year", d.dt.year.astype("Int64"))
        _fill(df, "month", d.dt.month.astype("Int64"))
        _fill(df, "quarter", ("Q" + d.dt.quarter.astype("Int64").astype("string")))


def _fill(df: pd.DataFrame, name: str, values: pd.Series) -> None:
    df[name] = values if name not in df else df[name].fillna(values)


def _fill_ids(df: pd.DataFrame, name: str, prefix: str) -> None:
    gen = pd.Series([f"{prefix}{i:08d}" for i in range(len(df))], index=df.index, dtype="string")
    _fill(df, name, gen)


# ── dimension derivation ────────────────────────────────────────────────────

def stub_dimensions(frames: dict, known: dict) -> tuple:
    """
    Facts may reference dealers/vehicles/customers that were not uploaded (or a
    sales-only upload). Build the missing dealer and vehicle rows from the facts
    so foreign keys hold; blank out customer references we cannot honour.
    `known` = ids already present in the tenant's tables (append mode).
    """
    notes = []
    facts = [frames[t] for t in ("sales", "inventory") if t in frames]

    def missing_ids(dim, col):
        have = set(known.get(dim, set())) | (set(frames[dim][col]) if dim in frames else set())
        need = set()
        for f in facts:
            if col in f:
                need |= set(f[col].dropna())
        return need - have

    new_dealers = missing_ids("dealers", "dealer_id")
    if new_dealers:
        src = pd.concat([f for f in facts if "dealer_id" in f], ignore_index=True)
        src = src[src["dealer_id"].isin(new_dealers)]
        agg = {"region": "first", "city": "first"}
        agg = {k: v for k, v in agg.items() if k in src}
        name_col = "dealer_name" if "dealer_name" in src else None
        if name_col:
            agg["dealer_name"] = "first"
        d = (src.groupby("dealer_id").agg(agg).reset_index() if agg
             else pd.DataFrame({"dealer_id": sorted(new_dealers)}))
        if not name_col:
            d["dealer_name"] = d["dealer_id"]
        frames["dealers"] = pd.concat([frames.get("dealers"), d], ignore_index=True) if "dealers" in frames else d
        notes.append(f"{len(d):,} dealer(s) created from your sales/inventory data")

    new_vehicles = missing_ids("vehicles", "vehicle_id")
    if new_vehicles:
        src = pd.concat([f for f in facts if "vehicle_id" in f], ignore_index=True)
        src = src[src["vehicle_id"].isin(new_vehicles)]
        agg = {c: "first" for c in ("brand", "model", "fuel_type") if c in src}
        v = src.groupby("vehicle_id").agg(agg).reset_index() if agg else pd.DataFrame({"vehicle_id": sorted(new_vehicles)})
        if "vehicle_category" in src:
            v["category"] = src.groupby("vehicle_id")["vehicle_category"].first().reindex(v["vehicle_id"]).values
        price_col = "base_price" if "base_price" in src else ("selling_price" if "selling_price" in src else None)
        if price_col:
            v["price"] = src.groupby("vehicle_id")[price_col].median().reindex(v["vehicle_id"]).values
        frames["vehicles"] = pd.concat([frames.get("vehicles"), v], ignore_index=True) if "vehicles" in frames else v
        notes.append(f"{len(v):,} vehicle(s) created from your sales/inventory data")

    if "sales" in frames and "customer_id" in frames["sales"]:
        have = set(known.get("customers", set())) | (set(frames["customers"]["customer_id"]) if "customers" in frames else set())
        s = frames["sales"]
        dangling = s["customer_id"].notna() & ~s["customer_id"].isin(have)
        if dangling.any():
            s.loc[dangling, "customer_id"] = pd.NA
            notes.append(f"{int(dangling.sum()):,} sale(s) referenced an unknown customer; customer link cleared")
    return frames, notes


# ── load ────────────────────────────────────────────────────────────────────

def _copy_insert(session, table: str, df: pd.DataFrame) -> int:
    cols = [c for c in df.columns if c in {c.name for c in MODELS[table].__table__.columns} and c != "tenant_id"]
    buf = io.StringIO()
    df[cols].to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    collist = ", ".join(f'"{c}"' for c in cols)
    stg = f"_stg_{table}"
    raw = session.connection().connection.driver_connection
    with raw.cursor() as cur:
        # Identifiers below come from our own model metadata (never from user input); values travel via COPY.
        cur.execute(f'CREATE TEMP TABLE "{stg}" (LIKE "{table}" INCLUDING DEFAULTS) ON COMMIT DROP')
        cur.copy_expert(f"COPY \"{stg}\" ({collist}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
        cur.execute(f'INSERT INTO "{table}" ({collist}) SELECT {collist} FROM "{stg}" ON CONFLICT DO NOTHING')  # noqa: S608 - identifiers from model metadata
        n = cur.rowcount
        cur.execute(f'DROP TABLE "{stg}"')
    return n


def _known_ids(session) -> dict:
    def q(model, col):
        return {r[0] for r in session.query(getattr(model, col)).all()}

    return {"dealers": q(Dealer, "dealer_id"), "vehicles": q(Vehicle, "vehicle_id"),
            "customers": q(Customer, "customer_id")}


def load_frames(tenant_id, frames: dict, replace: bool, progress=None) -> dict:
    """Load already-transformed frames for one tenant, atomically."""
    progress = progress or (lambda *a, **k: None)
    counts, notes = {}, []
    with tenant_context(tenant_id):
        session = get_db_session()
        try:
            if replace:
                progress("Clearing previous data", 0.62)
                for t in reversed(LOAD_ORDER):
                    session.query(MODELS[t]).delete()
            known = {} if replace else _known_ids(session)
            frames, notes = stub_dimensions(frames, known)
            todo = [t for t in LOAD_ORDER if t in frames]
            for i, t in enumerate(todo):
                progress(f"Loading {t.replace('_', ' ')}", 0.65 + 0.3 * i / max(len(todo), 1))
                counts[t] = _copy_insert(session, t, frames[t])
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    return {"loaded": counts, "notes": notes}


def run_ingest(tenant_id, files: dict, mappings: dict, replace: bool = True, units: dict = None,
               dayfirst: bool = False, decimal: str = ".", progress=None) -> dict:
    """
    files:    {table: path-or-buffer}   mappings: {table: mapping dict (see Proposal.to_mapping)}
    Returns {"tables": {table: report}, "loaded": {...}, "notes": [...]}. Raises IngestError.
    """
    progress = progress or (lambda *a, **k: None)
    if not any(t in files for t in REQUIRED_TABLES):
        raise IngestError("A sales file is required.")
    frames, reports = {}, {}
    todo = [t for t in LOAD_ORDER if t in files]
    for i, t in enumerate(todo):
        progress(f"Reading {t.replace('_', ' ')}", 0.05 + 0.5 * i / len(todo))
        raw = read_csv(files[t])
        frames[t], reports[t] = transform_table(t, raw, mappings[t], units, dayfirst, decimal)
    result = load_frames(tenant_id, frames, replace, progress)
    progress("Done", 1.0)
    return {"tables": reports, **result}
