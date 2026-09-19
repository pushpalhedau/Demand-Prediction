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

        # Display settings are changed only by operators (admin console, owner credentials). Remove the
        # customer-callable function an earlier version installed.
        conn.execute(text("DROP FUNCTION IF EXISTS update_own_tenant_config(jsonb)"))
