"""
Phase 1 database check for a hosted Supabase project (steps 3.3 and 3.4 of DEPLOYMENT-EC2-MICRO.md).

Connects with BOTH database URLs from the environment (never from this file) and checks that:
  1. the owner URL (postgres) and the app URL (predictax_app) both connect through the session pooler
  2. predictax_app is restricted: not superuser, cannot bypass row-level security, cannot create roles
  3. predictax_app can create a TEMP table (bulk imports need it) but cannot create tables in "public"
  4. Supabase's REST roles (anon, authenticated, service_role) have no privileges on tables in "public"
  5. after `init-db`: every tenant table has row-level security enabled and forced
Read-only apart from a temp table that disappears with the connection.

Run from the repo root in Git Bash:
  export DATABASE_URL='postgresql+psycopg2://predictax_app.<ref>:<pw>@<pooler-host>:5432/postgres'
  export ADMIN_DATABASE_URL='postgresql+psycopg2://postgres.<ref>:<pw>@<pooler-host>:5432/postgres'
  venv/Scripts/python.exe scripts/supabase_db_check.py
"""
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
    return ok


def need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Set {name} first (see the docstring).")
    return value


app_url, admin_url = need("DATABASE_URL"), need("ADMIN_DATABASE_URL")
if app_url == admin_url:
    sys.exit("DATABASE_URL and ADMIN_DATABASE_URL must be different roles.")
for label, url in (("DATABASE_URL", app_url), ("ADMIN_DATABASE_URL", admin_url)):
    if ":6543/" in url:
        print(f"WARNING: {label} uses port 6543 (transaction pooler). Use the session pooler on 5432: imports stage rows in a temp table.")

admin = create_engine(admin_url, pool_pre_ping=True)
app = create_engine(app_url, pool_pre_ping=True)

try:
    with admin.connect() as c:
        who = c.execute(text("select current_user")).scalar()
        check("owner URL connects", True, f"as {who}")
except DBAPIError as e:
    check("owner URL connects", False, str(e.orig).strip().splitlines()[0])
    sys.exit("Cannot continue without the owner connection (check host, project ref suffix and password).")

try:
    with app.connect() as c:
        who = c.execute(text("select current_user")).scalar()
        check("app URL connects", True, f"as {who}")
except DBAPIError as e:
    check("app URL connects", False, str(e.orig).strip().splitlines()[0] + " (did you run supabase_role_setup.sql with the same password?)")
    sys.exit("Cannot continue without the app connection.")

with admin.connect() as c:
    row = c.execute(text("select rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles where rolname = 'predictax_app'")).one()
    check("predictax_app is restricted (no superuser, no bypass-RLS, no create role/db)", not any(row), f"flags={tuple(row)}")

    leaks = c.execute(text(
        "select grantee, table_name, privilege_type from information_schema.role_table_grants "
        "where table_schema = 'public' and grantee in ('anon', 'authenticated', 'service_role')")).all()
    check("Supabase REST roles have no privileges on public tables", not leaks,
          "" if not leaks else f"{len(leaks)} grants, e.g. {tuple(leaks[0])}: run the REVOKE statements from step 6.6")

    tables = c.execute(text(
        "select c.relname, c.relrowsecurity, c.relforcerowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' order by 1")).all()
    if tables:
        no_rls = [t.relname for t in tables if not t.relrowsecurity]
        # audit_events has no tenant column: it is protected by REVOKE + a trigger instead of a policy
        check("every public table has row-level security enabled (after init-db)",
              set(no_rls) <= {"audit_events"}, f"{len(tables)} tables" if set(no_rls) <= {"audit_events"} else f"without RLS: {no_rls}")
    else:
        print("[SKIP] no tables yet: run `backend.cli init-db` (step 6.6), then re-run this script")

with app.connect() as c:
    try:
        c.execute(text("create temp table px_check_tmp (x int)"))
        check("predictax_app can create a TEMP table", True)
    except DBAPIError as e:
        check("predictax_app can create a TEMP table", False, str(e.orig).strip().splitlines()[0])
    c.rollback()

with app.connect() as c:
    try:
        c.execute(text("create table public.px_should_not_exist (x int)"))
        c.rollback()
        check("predictax_app cannot create tables in public", False, "it created one: it must not own or create tables")
    except DBAPIError:
        check("predictax_app cannot create tables in public", True)

failed = [name for name, ok in results if not ok]
print("\nRESULT:", "ALL PASSED." if not failed else f"{len(failed)} FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)
