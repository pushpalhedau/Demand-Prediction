from sqlalchemy import text

from backend.core.config import get_settings
from backend.db.connection import Base

# NULLIF: on a pooled connection that previously served a tenant, Postgres
# reverts the setting to '' (not unset), and ''::uuid would raise. NULL instead
# makes the policy match nothing, so an unscoped query returns zero rows.
TENANT_EXPR = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


TENANT_CONFIG_KEYS = ("currency", "currency_symbol", "symbol_position", "language",
                      "region_label", "country", "country_name", "news_hl", "news_gl")


def _app_role() -> str:
    return get_settings().app_db_role


def apply_rls(admin_engine) -> None:
    role = _app_role()
    with admin_engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            name = table.name
            if name == "tenants":
                col, force = "id", False   # owner keeps access for provisioning
            elif "tenant_id" in table.c:
                col, force = "tenant_id", True
            else:
                # Default-deny: a table that is not tenant-scoped (e.g. the audit trail) must never be reachable
                # by the customer-facing role, whatever default privileges the database grants.
                conn.execute(text(f'REVOKE ALL ON "{name}" FROM {role}'))
                continue

            conn.execute(text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{name}" {"FORCE" if force else "NO FORCE"} ROW LEVEL SECURITY'))
            conn.execute(text(f'DROP POLICY IF EXISTS tenant_isolation ON "{name}"'))
            conn.execute(text(
                f'CREATE POLICY tenant_isolation ON "{name}" '
                f'USING ({col} = {TENANT_EXPR}) WITH CHECK ({col} = {TENANT_EXPR})'
            ))
            privileges = "SELECT" if name == "tenants" else "SELECT, INSERT, UPDATE, DELETE"
            conn.execute(text(f'REVOKE ALL ON "{name}" FROM {role}'))
            conn.execute(text(f'GRANT {privileges} ON "{name}" TO {role}'))

        conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"))

        _install_audit_immutability(conn)

        # Display settings are changed only by operators (admin console, owner credentials). Remove the
        # customer-callable function an earlier version installed.
        conn.execute(text("DROP FUNCTION IF EXISTS update_own_tenant_config(jsonb)"))


def resync_sequences(admin_engine, tables: list[str] | None = None) -> dict[str, int]:
    """Move every serial id sequence past MAX(id), so rows loaded with explicit ids (restore, migration)
    cannot make later inserts collide on the primary key. Returns {table: new sequence value}.

    Tenant tables have FORCE ROW LEVEL SECURITY, so even the owner would only see the (unset) tenant's rows.
    FORCE is lifted and restored inside one transaction (transactional DDL) so MAX sees every tenant's rows.
    """
    import backend.db.models  # noqa: F401  (registers every table on Base.metadata)
    done: dict[str, int] = {}
    with admin_engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            name = table.name
            if tables is not None and name not in tables:
                continue
            pk = list(table.primary_key.columns)
            if len(pk) != 1 or not pk[0].autoincrement or pk[0].type.python_type is not int:
                continue
            col = pk[0].name
            seq = conn.execute(text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": name, "c": col}).scalar()
            if not seq:
                continue
            forced = "tenant_id" in table.c
            if forced:
                conn.execute(text(f'ALTER TABLE "{name}" NO FORCE ROW LEVEL SECURITY'))
            top = conn.execute(text(f'SELECT COALESCE(MAX("{col}"), 0) FROM "{name}"')).scalar()
            if forced:
                conn.execute(text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
            # is_called=true: the next value is top + 1 (an empty table restarts at 2, harmless).
            conn.execute(text("SELECT setval(CAST(:s AS regclass), :v, true)"), {"s": seq, "v": max(top, 1)})
            done[name] = top
    return done


def _install_audit_immutability(conn) -> None:
    """The audit trail is append-only: any UPDATE or DELETE on it is rejected by the database itself."""
    conn.execute(text("""
        CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events is append-only';
        END $$
    """))
    conn.execute(text("DROP TRIGGER IF EXISTS audit_events_no_change ON audit_events"))
    conn.execute(text("""
        CREATE TRIGGER audit_events_no_change BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_immutable()
    """))
    conn.execute(text("""
        CREATE OR REPLACE FUNCTION audit_events_no_truncate() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events is append-only';
        END $$
    """))
    conn.execute(text("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events"))
    conn.execute(text("""
        CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION audit_events_no_truncate()
    """))
