"""
VAHAN MCP Data Extractor
========================
Connects to the VAHAN MCP server and extracts Indian vehicle registration data.

Connection strategy (tried in order):
  1. Remote streamable HTTP  → https://vahanmcp.shubhamgrg.com/mcp
  2. Remote SSE              → same URL
  3. Local stdio             → clones shubhamgrg04/vahanmcp and runs mcp_server.py

The VAHAN MCP server's tools return plain-text tables (not JSON), so this
extractor parses those with _parse_text_table().  All heavy lifting is done
via run_sql to avoid N×M state×year request loops.

Outputs (saved alongside this script):
  registrations.csv  — monthly registrations: maker × month × state × year
  fuel_breakdown.csv — fuel type × vehicle class × state × year
  ev_stats.csv       — EV registrations per state per year
  rtos.csv           — all Regional Transport Offices (if available)

Usage:
  pip install mcp
  python vahan_extractor.py
"""

import asyncio
import csv
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR       = Path(__file__).parent
VAHAN_MCP_URL    = "https://vahanmcp.shubhamgrg.com/mcp"
LOCAL_REPO_DIR   = OUTPUT_DIR / "vahanmcp"
LOCAL_SERVER_PY  = LOCAL_REPO_DIR / "mcp_server.py"

# ─────────────────────────────────────────────────────────────────────────────
# Text-table parser (parses rows_to_text() output from the server)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_text_table(text: str) -> List[Dict]:
    """
    Parse a rows_to_text()-formatted table into a list of dicts.

    Format:
        col1 | col2 | col3
        ----- | ----- | -----
        val1 | val2 | val3
    """
    if not text or text.strip() in ("No results found.", ""):
        return []
    lines = [l for l in text.strip().split("\n") if l.strip()]
    # First line = headers, second line = separator (starts with '-'), rest = data
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[1:]:
        if line.lstrip().startswith("-"):      # skip separator line
            continue
        vals = [v.strip() for v in line.split("|")]
        if len(vals) == len(headers):
            rows.append(dict(zip(headers, vals)))
    return rows


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(str(val).replace(",", "").split(".")[0])
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# MCP tool caller (handles text-table responses)
# ─────────────────────────────────────────────────────────────────────────────

async def run_sql_query(client, sql: str, limit: int = 200000) -> List[Dict]:
    """Execute a SELECT via run_sql tool and return parsed rows."""
    result = await client.call_tool("run_sql", {"query": sql, "limit": limit})
    if not result or not result.content:
        return []
    text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
    rows = _parse_text_table(text)
    log.info("SQL returned %d rows", len(rows))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Extraction queries (run_sql for efficiency — no N×M loops)
# ─────────────────────────────────────────────────────────────────────────────

async def extract_registrations(client) -> List[Dict]:
    """Monthly maker-wise registrations for all states and all available years."""
    log.info("Extracting maker × month registrations...")
    rows = await run_sql_query(client, """
        SELECT
            yaxis_value   AS maker,
            xaxis_value   AS month,
            state,
            year,
            SUM(count)    AS registrations_count
        FROM vahan_data
        WHERE yaxis_name = 'Maker'
          AND xaxis_name = 'Month Wise'
        GROUP BY yaxis_value, xaxis_value, state, year
        ORDER BY year, state, yaxis_value, xaxis_value
        LIMIT 500000
    """)
    result = []
    for r in rows:
        result.append({
            "date":                _month_to_date(r.get("month", ""), r.get("year", "")),
            "state":               r.get("state", ""),
            "rto_code":            "",
            "maker":               r.get("maker", ""),
            "vehicle_class":       "",
            "fuel_type":           "",
            "registrations_count": _safe_int(r.get("registrations_count", 0)),
        })
    return result


async def extract_fuel_breakdown(client) -> List[Dict]:
    """Fuel type × vehicle class registrations per state per year."""
    log.info("Extracting fuel × vehicle class breakdown...")
    rows = await run_sql_query(client, """
        SELECT
            xaxis_value   AS fuel_type,
            yaxis_value   AS vehicle_class,
            state,
            year,
            SUM(count)    AS registrations_count
        FROM vahan_data
        WHERE xaxis_name = 'Fuel'
          AND yaxis_name = 'Vehicle Class'
        GROUP BY xaxis_value, yaxis_value, state, year
        ORDER BY year, state, xaxis_value, yaxis_value
        LIMIT 200000
    """)
    result = []
    for r in rows:
        result.append({
            "date":                f"{r.get('year', '2025')}-01-01",
            "state":               r.get("state", ""),
            "rto_code":            "",
            "maker":               "",
            "vehicle_class":       r.get("vehicle_class", ""),
            "fuel_type":           r.get("fuel_type", ""),
            "registrations_count": _safe_int(r.get("registrations_count", 0)),
        })
    return result


async def extract_ev_stats(client) -> List[Dict]:
    """EV registrations and share per state per year."""
    log.info("Extracting EV stats...")

    ev_rows = await run_sql_query(client, """
        SELECT state, year, SUM(count) AS ev_count
        FROM vahan_data
        WHERE (xaxis_name = 'Fuel' AND xaxis_value IN (
                  'PURE EV','PLUG-IN HYBRID EV','STRONG HYBRID EV','ELECTRIC(BOV)'
               ))
           OR (yaxis_name = 'Fuel' AND yaxis_value IN (
                  'PURE EV','PLUG-IN HYBRID EV','STRONG HYBRID EV','ELECTRIC(BOV)'
               ))
        GROUP BY state, year
        ORDER BY year, state
        LIMIT 5000
    """)

    total_rows = await run_sql_query(client, """
        SELECT state, year, SUM(count) AS total_count
        FROM vahan_data
        WHERE yaxis_name = 'Maker'
        GROUP BY state, year
        ORDER BY year, state
        LIMIT 5000
    """)

    # Build lookup: (state, year) → total
    totals = {(r.get("state", ""), r.get("year", "")): _safe_int(r.get("total_count", 0))
              for r in total_rows}

    result = []
    for r in ev_rows:
        state = r.get("state", "")
        year  = r.get("year", "")
        ev    = _safe_int(r.get("ev_count", 0))
        total = totals.get((state, year), 0)
        share = round(ev / total * 100, 4) if total > 0 else 0.0
        result.append({"year": year, "state": state, "ev_registrations": ev, "ev_share_pct": share})
    return result


async def extract_rtos(client) -> List[Dict]:
    """All RTO offices (if the rtos table exists in the DB)."""
    log.info("Extracting RTOs...")
    rows = await run_sql_query(client, """
        SELECT state_code, state_name, rto_code, rto_name
        FROM rtos
        ORDER BY state_code, rto_code
        LIMIT 5000
    """)
    return [{"state_code":  r.get("state_code", ""),
             "state_name":  r.get("state_name", ""),
             "rto_code":    r.get("rto_code", ""),
             "rto_name":    r.get("rto_name", "")} for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

def _month_to_date(month_label: str, year: Any) -> str:
    """Convert 'Jan', '01', 'January' etc. → 'YYYY-MM-01'."""
    try:
        yr = int(str(year))
    except (ValueError, TypeError):
        yr = 2025
    label = str(month_label).lower().strip()
    for abbr, num in _MONTH_MAP.items():
        if label.startswith(abbr):
            return f"{yr}-{num}-01"
    if label.isdigit() and 1 <= int(label) <= 12:
        return f"{yr}-{int(label):02d}-01"
    return f"{yr}-01-01"


def _write_csv(rows: List[Dict], path: Path, fieldnames: List[str]):
    if not rows:
        log.warning("No data to write to %s", path)
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows → %s", len(rows), path)


# ─────────────────────────────────────────────────────────────────────────────
# Extraction pipeline (runs once a session is established)
# ─────────────────────────────────────────────────────────────────────────────

async def run_extraction(session):
    await session.initialize()
    log.info("MCP session ready. Starting extraction...")

    # 1. Maker × Month registrations
    reg_rows = await extract_registrations(session)

    # 2. Fuel × Vehicle Class breakdown (appended to registrations.csv)
    fuel_rows = await extract_fuel_breakdown(session)

    all_reg_rows = reg_rows + fuel_rows
    _write_csv(all_reg_rows, OUTPUT_DIR / "registrations.csv",
               ["date", "state", "rto_code", "maker", "vehicle_class", "fuel_type", "registrations_count"])

    # 3. EV stats
    ev_rows = await extract_ev_stats(session)
    _write_csv(ev_rows, OUTPUT_DIR / "ev_stats.csv",
               ["year", "state", "ev_registrations", "ev_share_pct"])

    # 4. RTOs
    rto_rows = await extract_rtos(session)
    if rto_rows:
        _write_csv(rto_rows, OUTPUT_DIR / "rtos.csv",
                   ["state_code", "state_name", "rto_code", "rto_name"])
    else:
        log.info("No RTO table in DB — skipping rtos.csv")

    log.info("Extraction complete.")


# ─────────────────────────────────────────────────────────────────────────────
# Transport attempts
# ─────────────────────────────────────────────────────────────────────────────

async def _try_streamable_http():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    log.info("Trying remote streamable HTTP → %s", VAHAN_MCP_URL)
    async with streamablehttp_client(VAHAN_MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await run_extraction(session)


async def _try_sse():
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    log.info("Trying remote SSE → %s", VAHAN_MCP_URL)
    async with sse_client(VAHAN_MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await run_extraction(session)


async def _try_local_stdio():
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    log.info("Trying local stdio → %s", LOCAL_SERVER_PY)
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(LOCAL_SERVER_PY)],
        cwd=str(LOCAL_SERVER_PY.parent),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await run_extraction(session)


# ─────────────────────────────────────────────────────────────────────────────
# Local server setup
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_local_server() -> bool:
    """Clone the repo if needed and install deps. Returns True on success."""
    import subprocess

    if not LOCAL_REPO_DIR.exists():
        log.info("Cloning shubhamgrg04/vahanmcp → %s", LOCAL_REPO_DIR)
        r = subprocess.run(
            ["git", "clone", "https://github.com/shubhamgrg04/vahanmcp.git", str(LOCAL_REPO_DIR)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            log.error("git clone failed: %s", r.stderr)
            return False

    req = LOCAL_REPO_DIR / "requirements.txt"
    if req.exists():
        log.info("Installing deps from %s ...", req)
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            log.error("pip install failed: %s", r.stderr)
            return False

    return LOCAL_SERVER_PY.exists()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    try:
        from mcp import ClientSession  # noqa — verify install
    except ImportError:
        log.error("mcp not installed. Run: pip install mcp")
        sys.exit(1)

    # 1. Try remote transports
    for name, fn in [("streamable HTTP", _try_streamable_http), ("SSE", _try_sse)]:
        try:
            await fn()
            return
        except ImportError as e:
            log.warning("%s not available: %s", name, e)
        except Exception as e:
            log.warning("Remote %s failed: %s", name, e)

    log.warning("Remote server unreachable. Falling back to local stdio...")

    # 2. Ensure local server exists
    if not LOCAL_SERVER_PY.exists():
        if not _ensure_local_server():
            log.error("Could not set up local VAHAN MCP server. See README for manual steps.")
            sys.exit(1)

    # 3. Local stdio
    try:
        await _try_local_stdio()
    except Exception as e:
        log.error("Local stdio also failed: %s", e)
        import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
