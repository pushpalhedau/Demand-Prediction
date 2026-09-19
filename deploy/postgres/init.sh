#!/bin/sh
# Runs once, on first start of an empty data volume, as the bootstrap superuser (the table "owner").
#
# Roles created here:
#   predictax_app        the customer-facing app role. No superuser, no BYPASSRLS, cannot create objects, and is
#                        given access table by table by `python -m backend.cli init-db` (default-deny).
#   supabase_auth_admin  owns the auth schema used by the open-source Supabase Auth server.
#
# Passwords come from the environment (set them for anything but local development).
set -eu

: "${APP_DB_PASSWORD:=predictax_app_dev}"
: "${AUTH_DB_PASSWORD:=auth_dev_pw}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_pw="$APP_DB_PASSWORD" -v auth_pw="$AUTH_DB_PASSWORD" -v dbname="$POSTGRES_DB" <<'SQL'
-- Nobody gets anything by default.
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE ROLE predictax_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT, TEMPORARY ON DATABASE :"dbname" TO predictax_app;   -- TEMPORARY: bulk imports stage rows in a temp table
GRANT USAGE ON SCHEMA public TO predictax_app;
-- No ALTER DEFAULT PRIVILEGES on purpose: each table the app may touch is granted explicitly (and every other
-- table explicitly revoked) by init-db, so a new table is invisible to the app until someone decides otherwise.

CREATE ROLE supabase_auth_admin LOGIN PASSWORD :'auth_pw' NOINHERIT CREATEROLE;
GRANT CONNECT ON DATABASE :"dbname" TO supabase_auth_admin;
GRANT CREATE ON DATABASE :"dbname" TO supabase_auth_admin;
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_auth_admin;
ALTER ROLE supabase_auth_admin SET search_path = auth;

-- The auth server's migrations grant to Supabase's standard roles; they only need to exist (no login).
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['postgres','anon','authenticated','service_role','supabase_admin'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN EXECUTE format('CREATE ROLE %I NOLOGIN', r); END IF;
  END LOOP;
END $$;
SQL
