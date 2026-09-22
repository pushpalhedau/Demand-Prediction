# Architecture

## Shape of the system

```
 browser ──► web app (Next.js): dashboard + /admin ──/api──► backend.api (FastAPI) ─┐   web/  + backend/api
 browser ──► standalone admin console (Next.js)    ──/api──► backend.api (FastAPI) ─┤   web-admin/  (optional, private)
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
| 8 | `services` | application services used by the API |
| 9 | `api` | HTTP shell for both web apps: cookie sessions, tenant binding, JSON; calls only `services` |

## Tenancy: how one customer never sees another's data

One shared PostgreSQL database. Every business table has a `tenant_id` and **row-level security** (RLS) policies
that compare it with the tenant the current transaction is pinned to.

1. After login, the auth server's signed token carries a `tenant_id` claim that only a service credential can set.
2. The API binds the scope once per request (`backend/api/deps.py`). The scope lives in `ContextVar`s, so concurrent
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

The two web apps use separate cookie names (`px_access`/`px_refresh` vs `px_admin_access`/`px_admin_refresh`, see
`backend/api/cookies.py`) and separate FastAPI dependencies (`deps.customer` vs `deps.operator`), so a browser that
somehow has both apps open at once can never have one session mistaken for the other.

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

## Request flow

`cookie → verify token → bind tenant scope → router → service → repository → Postgres`, and the scope is cleared
afterwards. Routers receive plain data (DataFrames, dicts) and never a session or an ORM object.

## Key decisions

* **A services layer behind a thin HTTP API**: the web apps cannot touch the database or another tenant; everything
  they do passes through `backend.services`.
* **Postgres RLS over per-tenant databases**: one schema to migrate and one pool at thousands of tenants; the
  database, not application code, enforces isolation.
* **Operator-run onboarding**: quality control over mappings and no upload surface on the customer side.
* **Free by construction**: Postgres, Redis, GoTrue, RSS news and an offline scorer; paid scoring is opt-in.

## Web dashboard (Next.js) and API

`web/` is a Next.js (React, TypeScript, Tailwind) app built on shadcn/ui components; charts are shadcn charts (Recharts). It is a client of `backend/api`, never of the database.

* **One origin.** The browser talks only to the Next.js server; it proxies `/api/*` to FastAPI, so the API needs no
  CORS and its cookies are first-party.
* **Sessions** are `httpOnly`, `SameSite=Strict` cookies (`Secure` in production) set by `/api/auth/login`; no token
  is ever readable by page scripts. An expired access token is refreshed once, transparently, from the refresh cookie.
* **CSRF:** every state-changing request must carry `X-Requested-With: predictax` (a cross-site form cannot add it).
* **Tenant scope** is bound per request in `backend/api/deps.py` from the verified token, and cleared afterwards. Postgres RLS remains the final guard; tests prove two tenants
  interleaved on the same workers never see each other's data.
* **Presentation** (currency, separators, language) is done in the browser from the tenant profile the API returns;
  the API returns raw numbers. Translations live in `web/src/i18n/*.json`.
* **Structure:** `components/ui` (shadcn primitives), `components/{layout,filters,data,charts}` (our shell, KPI card, panel,
  table and chart helpers), `features/<tab>` (one folder per dashboard), `lib` (API client, filters in the URL, i18n,
  formatting). Light/dark themes come from CSS variables in `app/globals.css`.
* **Store Performance map:** an SVG map drawn with `d3-geo` from region-boundary files in `web/src/data/regions/` (US states, German
  Länder, UAE emirates; Natural Earth, public domain, built by `scripts/build_region_maps.py`). It uses only theme colours, so it follows
  light/dark mode, and loads no tiles or external service. The right country is picked by matching the rooftops' region names; a country
  without a boundary file falls back to plain rooftop positions. To add a country, add it to `COUNTRIES` in the script and rebuild.
* **Tests:** unit tests cover formatting, translations (every key used exists in English and German) and URL safety.
* **Migration:** all seven customer tabs are ported.

## Admin console (Next.js)

The console lives in `web/src/admin/` and is served by the web app under `/admin` (routes in `web/src/app/admin/`). `web-admin/` is the
previous standalone build of the same console and still works on its own port. It offers: accounts, settings, logins, access (suspend/reactivate), import,
retrain and the audit log, all through `backend/api/routers/admin_*.py` (its own `/api/admin/*` surface, also
calling only `backend.services`). It is operator-only, English-only, and has no charts, so it does not depend on Recharts. It replaced the original Streamlit console,
which has been removed.

* **One login page for both kinds of user.** `POST /api/auth/login` checks the password once, then reads the account's `app_metadata`
  (writable only with the service-role key) to decide: `platform_admin` with no tenant is an operator (admin cookies, redirect to `/admin`);
  anything else must belong to an active tenant (customer cookies, redirect to `/`). `backend/services/identity.py: sign_in`. The two
  cookie namespaces stay separate and signing in as one kind clears the other, so a browser never holds both.
* **Publishing the web app publishes the console.** Serve the standalone `web-admin/` build privately instead (its own container,
  `admin-frontend`, port 3002, reached over a VPN or SSH tunnel) if you need the console off the internet.
* **Idle sign-out.** Operators are signed out after 30 minutes idle; `web-admin/src/lib/idle.ts`
  enforces that in the browser (a passive activity listener, checked every 30s).
* **One-time credentials.** A generated password (new account, new login, a reset) is handed to the page exactly
  once, across the redirect, via `sessionStorage` (`web-admin/src/lib/flash.ts`) — never state that could survive a
  re-render or reach the server.
* **Import wizard** (`backend/api/routers/admin_imports.py`, `web-admin/src/features/accounts/import/`): upload
  per table, an auto-proposed column mapping the operator can override (with unit-conversion presets and saved-
  mapping recall from the last import), a dry run on a sample, then the same background job and progress polling
  the retrain button uses. The job id is a client-generated UUID that doubles as the upload folder key, so an
  abandoned wizard session can never collide with a later one. The field catalog, table order and unit-conversion
  constants come from `GET /api/admin/imports/schema` — the wizard has no schema knowledge baked into its own code.
