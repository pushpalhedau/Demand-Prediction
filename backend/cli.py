import argparse
import sys

from backend.db.connection import Base, get_admin_engine, init_all_tables
from backend.tenancy.loader import load_csv_dir
import json

from backend.tenancy.provision import create_operator, add_user, create_tenant, get_tenant_id, list_tenants, set_config
from backend.ml.training import train_tenant_models


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m tenancy.cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Create tables and apply row-level security (owner credentials)")
    r = sub.add_parser("reset-db", help="DROP every table (dev only) and recreate the schema")
    r.add_argument("--yes", action="store_true", help="required: confirms all tenant data will be destroyed")
    sub.add_parser("list", help="List tenants")

    c = sub.add_parser("create-tenant", help="Create a tenant and its first admin login")
    c.add_argument("--slug", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--admin-email", required=True)
    c.add_argument("--password", help="Generated if omitted")
    c.add_argument("--currency", default="EUR")
    c.add_argument("--currency-symbol", default="€")
    c.add_argument("--language", default="en", choices=["en", "de"])
    c.add_argument("--no-login", action="store_true", help="Create the tenant row only (no Supabase user)")

    u = sub.add_parser("create-user", help="Add a login to an existing tenant")
    u.add_argument("--tenant", required=True, help="tenant slug")
    u.add_argument("--email", required=True)
    u.add_argument("--password", help="Generated if omitted")
    u.add_argument("--role", default="tenant_user", choices=["tenant_admin", "tenant_user"])

    op = sub.add_parser("create-operator", help="Create an admin-console operator login")
    op.add_argument("--email", required=True)
    op.add_argument("--password", help="Generated if omitted")

    sc = sub.add_parser("set-config", help="Merge JSON display settings into a tenant's config")
    sc.add_argument("--tenant", required=True, help="tenant slug")
    sc.add_argument("--json", required=True, help="JSON object, e.g. region_label / country_name / news_gl")

    l = sub.add_parser("load-csv", help="Load a folder of standard CSVs into a tenant")
    l.add_argument("--tenant", required=True, help="tenant slug")
    l.add_argument("--dir", required=True)
    l.add_argument("--append", action="store_true", help="Keep existing rows instead of replacing")
    l.add_argument("--distance", choices=["km", "mi"], help="Unit of unlabeled distance columns (auto-detected if omitted)")
    l.add_argument("--dayfirst", action="store_true", help="Dates are DD/MM/YYYY")
    l.add_argument("--decimal", default=".", choices=[".", ","], help="Decimal separator in numbers")

    t = sub.add_parser("train", help="Train a tenant's ML models")
    t.add_argument("--tenant", required=True, help="tenant slug")

    a = p.parse_args(argv)

    if a.cmd == "init-db":
        init_all_tables()
        print("Schema and row-level security are up to date.")
    elif a.cmd == "reset-db":
        if not a.yes:
            sys.exit("Refusing: pass --yes to confirm all data will be destroyed.")
        import backend.db.models  # noqa: F401
        Base.metadata.drop_all(get_admin_engine())
        init_all_tables()
        print("Database reset.")
    elif a.cmd == "list":
        for row in list_tenants():
            print("  ".join(row))
    elif a.cmd == "create-tenant":
        r = create_tenant(
            a.slug, a.name, a.admin_email, a.password,
            config={"currency": a.currency, "currency_symbol": a.currency_symbol, "language": a.language},
            create_login=not a.no_login,
        )
        print(f"Created tenant {r['slug']} ({r['tenant_id']})")
        if r["password"]:
            print(f"Login: {r['email']} / {r['password']}   (shown once)")
    elif a.cmd == "create-user":
        r = add_user(a.tenant, a.email, a.password, a.role)
        print(f"Created {r['role']} {r['email']} for {a.tenant}   password: {r['password']}   (shown once)")
    elif a.cmd == "create-operator":
        r = create_operator(a.email, a.password)
        print(f"Operator {r['email']}   password: {r['password']}   (shown once)")
    elif a.cmd == "set-config":
        print(set_config(a.tenant, json.loads(a.json)))
    elif a.cmd == "load-csv":
        load_csv_dir(get_tenant_id(a.tenant), a.dir, replace=not a.append,
                     units={"distance": a.distance} if a.distance else None,
                     dayfirst=a.dayfirst, decimal=a.decimal)
    elif a.cmd == "train":
        train_tenant_models(get_tenant_id(a.tenant))


if __name__ == "__main__":
    sys.exit(main())
