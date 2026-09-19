# Architecture

## Shape of the system

```
 browser ──► customer app  (Streamlit)  ─┐
 browser ──► admin console (Streamlit)  ─┤   frontend/   (presentation only)
                                          ▼
                                   backend.services      ◄── the only door into the backend
                                          │
        ┌─────────────┬───────────────────┼──────────────┬──────────────┐
        ▼             ▼                   ▼              ▼              ▼
   repositories   analytics / ml     ingestion       tenancy         sentiment
        │             │                   │              │              │
        └──────► backend.db (engines, RLS, ORM) ◄─────────┘              │
                          │                                              │
                     PostgreSQL                          news feeds (RSS, public)
        auth server (GoTrue) ── users live in the same Postgres, own schema
        Redis + RQ worker ── background imports and retraining
```

Layers (a package may import only from its own layer or one BELOW it; enforced by a test):

| # | package | responsibility |
|---|---|---|
| 0 | `core` | config, request scope, formatting, cache, errors, logging, security primitives |
| 1 | `db` | engines, sessions, row-level security, ORM models |
| 2 | `repositories`, `auth` | SQL by domain; the auth-server client |
| 3 | `analytics` | decision engine, YoY attribution, what-if model |
| 4 | `sentiment` | news intake, offline scoring, briefing |
| 5 | `ml` | forecasting, segmentation, lead scoring, signed artifacts |
| 6 | `ingestion` | field catalog, mapping, transform + load, jobs |
| 7 | `tenancy` | provisioning, capabilities, settings validation, audit |
| 8 | `services` | application services used by the frontend |

## Tenancy: how one customer never sees another's data

One shared PostgreSQL database. Every business table has a `tenant_id` and **row-level security** (RLS) policies
that compare it with the tenant the current transaction is pinned to.

1. After login, the auth server's signed token carries a `tenant_id` claim that only a service credential can set.
2. The frontend calls `bind_request(profile)` once per page run. The scope lives in `ContextVar`s, so concurrent
   sessions cannot see each other's.
3. Every transaction on the app engine runs `set_config('app.current_tenant_id', <id>, true)` first
   (transaction-local, so safe with connection pooling).
4. Postgres appends `tenant_id = current tenant` to every read and checks it on every write, regardless of what the
   SQL says. With no tenant bound the setting is empty and queries return zero rows (fail closed).
5. The app connects as a role that cannot bypass RLS, cannot create objects, and only has grants on tables that are
   explicitly meant for it. Everything else (`audit_events`, future tables) is default-deny.

Caches are keyed by tenant (`backend.core.cache`), model files live under a per-tenant directory, uploads under
`<UPLOAD_DIR>/<tenant_id>/`, and news is fetched once per country/language edition and shared, because it is public.

## Two kinds of login

* **Customer users** belong to one tenant. The customer app accepts only tokens that carry a tenant.
* **Operators** run the admin console and belong to no tenant (`platform_admin` role). The console accepts only
  those, and a customer token is refused with the same message as a wrong password.

## Market-neutral data model

Customers differ in country, currency, language and column names, but not in code. The schema has no currency in any
column name; units are stored metric; source columns with no canonical field are kept in a per-row `extras` JSON.
`backend/ingestion/catalog.py` is the single source of truth for fields, synonyms and unit conversions, and is
checked against the ORM models by a test. Per-tenant settings (currency, symbol, language, region label, news
edition) live in `tenants.config` and reach the UI through the request scope.

## Importing data

```
operator uploads CSVs ──► column mapping proposed (exact > unit-converted > synonym; guesses never auto-applied)
        │                        operator confirms / edits, runs a dry run on a sample
        ▼
   background job (thread, or Redis/RQ worker) re-scopes itself to the tenant:
   read → map + convert units → validate → derive missing dealers/vehicles → COPY into a temp table
   → INSERT … SELECT (RLS checks every row) → retrain models
```

The load is atomic: any failure loads nothing. Optional files unlock optional tabs; a sales file alone is enough.

## Request flow (customer app)

`reset scope → require_login → bind scope → capabilities → filters → view → service → repository → Postgres`.
Views receive plain data (DataFrames, dicts) and never a session or an ORM object.

## Key decisions

* **Services layer, one process** rather than an HTTP API: the frontend cannot touch the database or another tenant,
  and the seam is exactly where an API would attach later.
* **Postgres RLS over per-tenant databases**: one schema to migrate and one pool at thousands of tenants; the
  database, not application code, enforces isolation.
* **Operator-run onboarding**: quality control over mappings and no upload surface on the customer side.
* **Free by construction**: Postgres, Redis, GoTrue, RSS news and an offline scorer; paid scoring is opt-in.
