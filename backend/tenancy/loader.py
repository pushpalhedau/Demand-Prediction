import os

from backend.ingestion.mapping import propose_mapping
from backend.ingestion.pipeline import IngestError, read_csv, run_ingest
from backend.ingestion.catalog import LOAD_ORDER


def auto_mappings(files: dict) -> tuple:
    """Propose a mapping per file using only high-confidence matches. Returns (mappings, imperial_hint)."""
    mappings, imperial = {}, False
    for table, path in files.items():
        cols = list(read_csv(path).columns)
        p = propose_mapping(table, cols)
        if p.missing_required:
            raise IngestError(f"{table}: could not find required column(s) {p.missing_required} in {cols}")
        mappings[table] = p.to_mapping()
        imperial = imperial or p.imperial_hint
    return mappings, imperial


def load_csv_dir(tenant_id, directory: str, replace: bool = True, units: dict = None,
                 dayfirst: bool = False, decimal: str = ".", log=print) -> dict:
    """Load whichever of the six standard CSVs exist in a folder, using auto-detected column mapping."""
    files = {t: os.path.join(directory, f"{t}.csv") for t in LOAD_ORDER
             if os.path.exists(os.path.join(directory, f"{t}.csv"))}
    mappings, imperial = auto_mappings(files)
    if units is None:
        units = {"distance": "mi" if imperial else "km"}
    log(f"  files: {', '.join(files)} | distance unit: {units['distance']}")
    result = run_ingest(tenant_id, files, mappings, replace=replace, units=units,
                        dayfirst=dayfirst, decimal=decimal)
    for t, r in result["tables"].items():
        log(f"  {t}: {r['rows_out']:,} rows"
            + (f" | extras: {len(r.get('extras_columns', []))} col(s)" if r.get("extras_columns") else "")
            + (f" | failures: {r['coercion_failures']}" if r["coercion_failures"] else ""))
        for w in r["warnings"]:
            log(f"    ! {w}")
    for n in result["notes"]:
        log(f"  note: {n}")
    return result
