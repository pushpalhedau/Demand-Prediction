-- Runs once on first container start, as the bootstrap superuser (the "owner").
-- The app connects as predictax_app: no superuser, no BYPASSRLS, so row-level
-- security policies are always enforced against it.
CREATE ROLE predictax_app LOGIN PASSWORD 'predictax_app_dev' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE predictax TO predictax_app;
GRANT USAGE ON SCHEMA public TO predictax_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO predictax_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO predictax_app;

-- Open-source Supabase Auth (GoTrue) keeps its users in its own schema, owned by its own role.
-- The app role has no access to it.
CREATE ROLE supabase_auth_admin LOGIN PASSWORD 'auth_dev_pw' NOINHERIT CREATEROLE;
GRANT CREATE ON DATABASE predictax TO supabase_auth_admin;
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_auth_admin;
ALTER ROLE supabase_auth_admin SET search_path = auth;

-- GoTrue's migrations grant to Supabase's standard roles; they only need to exist (no login).
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['postgres','anon','authenticated','service_role','supabase_admin'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN EXECUTE format('CREATE ROLE %I NOLOGIN', r); END IF;
  END LOOP;
END $$;
