"""
extract_past_years_data.py
==========================
One-click script to scrape historical VAHAN registration data (2019-2024)
from the live VAHAN dashboard and merge it with the existing 2025-2026 data.

Pipeline:
  Step 1 -- Pre-flight checks (playwright, Chromium, VAHAN site reachability)
  Step 2 -- For each target year x axis combination, run vahan_scraper.py
            (skips CSVs that already exist -> fully resumable)
  Step 3 -- Delete the MCP server's SQLite DB so all CSVs get re-ingested fresh
  Step 4 -- Run vahan_extractor.py to produce the final registrations.csv
            covering 2019-2026

Usage:
  python extract_past_years_data.py                    # scrape 2019-2024
  python extract_past_years_data.py --years 2022 2023  # specific years only
  python extract_past_years_data.py --skip-extractor   # scrape only, no CSV merge

Time estimate: ~25-40 min per year (36 states x 2 axis combos x ~30s/state).
               Full 2019-2024 run ~ 3-5 hours. Leave it running overnight.
"""

import argparse
import os
import sys
import subprocess
import time
import shutil
from datetime import datetime
from pathlib import Path

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).parent.resolve()
REPO_DIR      = SCRIPT_DIR / "vahanmcp"
SCRAPER_PY    = REPO_DIR / "scraping" / "vahan_scraper.py"
DATA_DIR      = REPO_DIR / "data"
DB_PATH       = REPO_DIR / "db" / "vahan.db"
EXTRACTOR_PY  = SCRIPT_DIR / "vahan_extractor.py"
PYTHON        = sys.executable   # use the same venv python

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DEFAULT_YEARS = list(range(2019, 2025))   # 2019, 2020, 2021, 2022, 2023, 2024

# Each tuple is (xaxis, yaxis) -- produces {Xaxis}_{Yaxis}_{year}.csv
# These two cover everything our project needs:
#   - Monthly maker registrations  -> Prophet forecasting + Overview KPIs
#   - Fuel x Vehicle Class         -> Fuel distribution charts
AXIS_COMBOS = [
    ("Month Wise",   "Maker"),
    ("Fuel",         "Vehicle Class"),
    ("Month Wise",   "Vehicle Class"),
    ("Month Wise",   "Fuel"),
]

# Subprocess timeout per scraper call (seconds).
# Worst case: 36 states x 40s = 1440s. Add buffer -> 2 hours.
SCRAPER_TIMEOUT_SECONDS = 7200

# -----------------------------------------------------------------------------
# Console helpers
# -----------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def header(msg: str):
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {msg}")
    print(f"{bar}")


def step(n: int, msg: str):
    print(f"\n[{_now()}] -- Step {n}: {msg}")


def ok(msg: str):
    print(f"[{_now()}]  OK  {msg}")


def warn(msg: str):
    print(f"[{_now()}]  WARN  {msg}")


def err(msg: str):
    print(f"[{_now()}]  FAIL  {msg}", file=sys.stderr)


def info(msg: str):
    print(f"[{_now()}]     {msg}")


# -----------------------------------------------------------------------------
# Step 1 -- Pre-flight checks
# -----------------------------------------------------------------------------

def preflight() -> bool:
    header("Pre-flight checks")
    all_ok = True

    # Playwright importable?
    try:
        from playwright.sync_api import sync_playwright  # noqa
        ok("playwright package found")
    except ImportError:
        err("playwright not installed. Run:  pip install playwright")
        all_ok = False

    # Chromium browser available?
    if all_ok:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True)
                b.close()
            ok("Chromium browser found")
        except Exception as e:
            err(f"Chromium not installed: {e}")
            err("Run:  playwright install chromium")
            all_ok = False

    # Scraper script exists?
    if SCRAPER_PY.exists():
        ok(f"vahan_scraper.py found at {SCRAPER_PY}")
    else:
        err(f"vahan_scraper.py not found at {SCRAPER_PY}")
        err("Make sure the vahanmcp repo is cloned inside automobile_datasets/india/")
        all_ok = False

    # Data directory writable?
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ok(f"Data directory ready: {DATA_DIR}")

    # VAHAN site reachable?
    try:
        import urllib.request
        urllib.request.urlopen(
            "https://vahan.parivahan.gov.in/vahan4dashboard/",
            timeout=10
        )
        ok("VAHAN dashboard is reachable")
    except Exception as e:
        warn(f"VAHAN site connectivity check failed: {e}")
        warn("Continuing anyway -- scraper has its own retry logic")

    return all_ok


# -----------------------------------------------------------------------------
# Step 2 -- Run scraper per year x axis combo
# -----------------------------------------------------------------------------

def _csv_name(xaxis: str, yaxis: str, year: int) -> str:
    """Mirror the filename the scraper produces: {X}_{Y}_{year}.csv"""
    def sanitize(t):
        return "".join(c if c.isalnum() else "_" for c in t).strip("_")
    return f"{sanitize(xaxis)}_{sanitize(yaxis)}_{year}.csv"


def _csv_exists(xaxis: str, yaxis: str, year: int) -> bool:
    return (DATA_DIR / _csv_name(xaxis, yaxis, year)).exists()


def run_scraper(year: int, xaxis: str, yaxis: str, retry: int = 2) -> bool:
    """
    Run vahan_scraper.py for one (year, xaxis, yaxis) combination.
    Returns True on success, False after all retries exhausted.
    """
    csv_path = DATA_DIR / _csv_name(xaxis, yaxis, year)

    if _csv_exists(xaxis, yaxis, year):
        ok(f"Already have {csv_path.name} -- skipping")
        return True

    info(f"Scraping  year={year}  X={xaxis}  Y={yaxis} ...")
    cmd = [
        PYTHON, str(SCRAPER_PY),
        "--year",  str(year),
        "--xaxis", xaxis,
        "--yaxis", yaxis,
        "--out",   str(DATA_DIR),
    ]

    for attempt in range(1, retry + 2):   # 1-based, total = retry+1 attempts
        if attempt > 1:
            wait = 30 * (attempt - 1)
            warn(f"Retry {attempt} for {year}/{xaxis}/{yaxis} in {wait}s ...")
            time.sleep(wait)

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                timeout=SCRAPER_TIMEOUT_SECONDS,
                cwd=str(REPO_DIR),
                capture_output=False,   # show output live
            )
            elapsed = round(time.monotonic() - t0)

            if result.returncode == 0 and csv_path.exists():
                rows = _count_csv_rows(csv_path)
                ok(f"Saved {csv_path.name}  ({rows:,} rows, {elapsed}s)")
                return True

            warn(f"Scraper exited with code {result.returncode} (took {elapsed}s)")

        except subprocess.TimeoutExpired:
            warn(f"Scraper timed out after {SCRAPER_TIMEOUT_SECONDS}s")
        except Exception as e:
            warn(f"Scraper raised exception: {e}")

    err(f"All attempts failed for year={year} X={xaxis} Y={yaxis}")
    return False


def _count_csv_rows(path: Path) -> int:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f) - 1  # minus header
    except Exception:
        return 0


def scrape_all_years(years: list) -> dict:
    """
    Run scraper for every year x axis combo.
    Returns summary: {year: {combo_str: bool}}
    """
    header(f"Scraping VAHAN data for years: {years}")
    total_combos = len(years) * len(AXIS_COMBOS)
    done = 0
    summary = {}

    for year in sorted(years):
        summary[year] = {}
        info(f"\n{'-'*50}")
        info(f"Year {year}  ({len(AXIS_COMBOS)} axis combos)")
        info(f"{'-'*50}")

        for xaxis, yaxis in AXIS_COMBOS:
            combo_label = f"{xaxis} x {yaxis}"
            success = run_scraper(year, xaxis, yaxis)
            summary[year][combo_label] = success
            done += 1
            pct = round(done / total_combos * 100)
            info(f"Overall progress: {done}/{total_combos} ({pct}%)")

    return summary


# -----------------------------------------------------------------------------
# Step 3 -- Delete stale SQLite DB so MCP server re-ingests everything
# -----------------------------------------------------------------------------

def reset_mcp_db():
    header("Resetting MCP server database (forcing full re-ingestion)")
    if DB_PATH.exists():
        backup = DB_PATH.with_suffix(".db.bak")
        shutil.copy2(DB_PATH, backup)
        DB_PATH.unlink()
        ok(f"Deleted {DB_PATH.name}  (backup -> {backup.name})")
    else:
        ok("DB does not exist yet -- nothing to delete")


# -----------------------------------------------------------------------------
# Step 4 -- Run vahan_extractor.py to produce registrations.csv
# -----------------------------------------------------------------------------

def run_extractor() -> bool:
    header("Running vahan_extractor.py -> registrations.csv")
    if not EXTRACTOR_PY.exists():
        err(f"vahan_extractor.py not found at {EXTRACTOR_PY}")
        return False

    info("This will start the local VAHAN MCP server and run all SQL queries ...")
    t0 = time.monotonic()
    result = subprocess.run(
        [PYTHON, str(EXTRACTOR_PY)],
        cwd=str(SCRIPT_DIR),
    )
    elapsed = round(time.monotonic() - t0)

    if result.returncode == 0:
        reg_csv = SCRIPT_DIR / "registrations.csv"
        if reg_csv.exists():
            rows = _count_csv_rows(reg_csv)
            ok(f"registrations.csv ready: {rows:,} rows ({elapsed}s)")
        else:
            warn("vahan_extractor.py exited 0 but registrations.csv not found")
        return True

    err(f"vahan_extractor.py failed (exit code {result.returncode}, {elapsed}s)")
    return False


# -----------------------------------------------------------------------------
# Summary printer
# -----------------------------------------------------------------------------

def print_summary(scrape_summary: dict, extractor_ok: bool):
    header("Run Summary")

    total = sum(len(v) for v in scrape_summary.values())
    passed = sum(1 for v in scrape_summary.values() for ok_ in v.values() if ok_)
    failed = total - passed

    for year, combos in sorted(scrape_summary.items()):
        year_ok = all(combos.values())
        status = "OK" if year_ok else "PARTIAL"
        print(f"  {year}: {status}")
        for combo, success in combos.items():
            mark = "OK" if success else "FAILED"
            print(f"      {mark}  {combo}")

    print()
    print(f"  Scraped:    {passed}/{total} combos succeeded")
    print(f"  Failed:     {failed} combos")
    print(f"  Extractor:  {'OK OK' if extractor_ok else 'FAIL FAILED'}")

    if failed == 0 and extractor_ok:
        print("\n  All done! registrations.csv covers 2019-2026.")
    elif failed > 0:
        print("\n  Re-run this script to retry failed years -- already-done CSVs are skipped.")

    # List all CSVs now present in data/
    csvs = sorted(DATA_DIR.glob("*.csv"))
    print(f"\n  CSVs in vahanmcp/data/ ({len(csvs)} files):")
    for p in csvs:
        print(f"    {p.name}")


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract historical VAHAN data (2019-2024) and rebuild registrations.csv"
    )
    parser.add_argument(
        "--years", nargs="+", type=int, default=DEFAULT_YEARS,
        help=f"Years to scrape (default: {DEFAULT_YEARS})"
    )
    parser.add_argument(
        "--skip-extractor", action="store_true",
        help="Stop after scraping -- do not re-run vahan_extractor.py"
    )
    parser.add_argument(
        "--only-extractor", action="store_true",
        help="Skip scraping and only re-run vahan_extractor.py (use when CSVs already exist)"
    )
    args = parser.parse_args()

    start_ts = time.monotonic()
    header("VAHAN Historical Data Extractor  |  extract_past_years_data.py")
    info(f"Target years : {sorted(args.years)}")
    info(f"Axis combos  : {[f'{x} x {y}' for x, y in AXIS_COMBOS]}")
    info(f"Data dir     : {DATA_DIR}")

    # -- Step 1: pre-flight ------------------------------------------------
    if not args.only_extractor:
        if not preflight():
            err("Pre-flight checks failed. Fix the issues above and re-run.")
            sys.exit(1)

    # -- Step 2: scrape ----------------------------------------------------
    scrape_summary = {}
    if not args.only_extractor:
        scrape_summary = scrape_all_years(sorted(args.years))
    else:
        info("--only-extractor flag set -- skipping scraping")

    # -- Step 3: reset DB --------------------------------------------------
    if not args.skip_extractor:
        reset_mcp_db()

    # -- Step 4: extractor -------------------------------------------------
    extractor_ok = True
    if not args.skip_extractor:
        extractor_ok = run_extractor()

    # -- Summary -----------------------------------------------------------
    elapsed_total = round(time.monotonic() - start_ts)
    h, m, s = elapsed_total // 3600, (elapsed_total % 3600) // 60, elapsed_total % 60
    print_summary(scrape_summary, extractor_ok)
    print(f"\n  Total time: {h}h {m}m {s}s")


if __name__ == "__main__":
    main()
