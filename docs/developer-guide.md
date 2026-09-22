# PredictaX developer guide

Everything an engineer needs to work on this project, in the order you need it: what the product is, the tech stack and why,
how the system fits together, how data flows through it, how it is secured, how to run and test it, and what to be careful of.

**Reading order.** Sections 1 to 3 orient you. Sections 4 to 6 are the foundations every change touches (layers, tenancy,
identity). Sections 7 to 10 follow the data. Sections 11 to 13 cover the two web apps, security and deployment. Sections 14 to
17 are the day-to-day (tests, running locally, recipes, gotchas). Section 18 is what is unfinished.

Contents

1. [What PredictaX is](#1-what-predictax-is)
2. [Tech stack, and why each piece](#2-tech-stack-and-why-each-piece)
3. [System architecture](#3-system-architecture)
4. [The backend, layer by layer](#4-the-backend-layer-by-layer)
5. [Multi-tenancy and the database](#5-multi-tenancy-and-the-database)
6. [Identity, sessions and access](#6-identity-sessions-and-access)
7. [Life of a request](#7-life-of-a-request)
8. [Data flow: getting a customer's data in](#8-data-flow-getting-a-customers-data-in)
9. [Analytics and machine learning](#9-analytics-and-machine-learning)
10. [Market sentiment](#10-market-sentiment)
11. [The two web apps](#11-the-two-web-apps)
12. [Security measures](#12-security-measures)
13. [Infrastructure and deployment](#13-infrastructure-and-deployment)
14. [Testing and quality gates](#14-testing-and-quality-gates)
15. [Working locally](#15-working-locally)
16. [Recipes: common changes](#16-recipes-common-changes)
17. [Demo data and datasets](#17-demo-data-and-datasets)
18. [Conventions, gotchas and known limitations](#18-conventions-gotchas-and-known-limitations)
19. [Glossary and file map](#19-glossary-and-file-map)

Related, shorter documents: [architecture.md](architecture.md), [security.md](security.md), [operations.md](operations.md),
and research notes in [research/](research/). This guide is the long form; if it disagrees with the code, the code wins.

---

## 1. What PredictaX is

PredictaX is a **multi-tenant demand-intelligence platform for automobile dealer groups**. A *tenant* (the code also says
*account* or *organisation*) is one dealer group. Its staff sign in and see dashboards built only from that group's own data:
forecasting, store performance, comparisons, customer intelligence, inventory and market sentiment.

**Who uses it, and how the two kinds of login differ**

| Kind | Who | Belongs to | Uses |
|---|---|---|---|
| Customer user | dealer-group staff | exactly one tenant | the customer dashboard (`web/`, port 3000) |
| Operator | PredictaX staff | no tenant (`platform_admin`) | the admin console, at `/admin` in the same web app (`web/src/admin/`); the older standalone `web-admin/` (port 3002) still works. One login page for both kinds: the account's `app_metadata` decides where you land |

**Onboarding is operator-run, on purpose.** Customers cannot upload data or edit settings. An operator creates the account,
imports the customer's CSV exports, checks the column mapping, and lets the platform train the models. This gives quality control
over mappings and means there is no upload surface on the customer side. The trade-off is that it does not scale to thousands of
accounts without effort; the engine underneath would support a self-serve mode later.

**The seven dashboard tabs** (each is shown only if the account has the data it needs):

| Tab | Route | Needs | What it answers |
|---|---|---|---|
| Executive Overview | `/` | sales | headline numbers, ranked recommended plays |
| Demand Forecasting | `/forecasting` | sales | forecast with confidence band, what-if market levers |
| Comparative Analytics | `/comparison` | sales, dealers | year-on-year tracking and the drivers of change |
| Store Performance | `/regional` | sales, dealers | every rooftop's pace against its target, and a region map |
| Customer Intelligence | `/customers` | sales, customers | retention queue, segments, lead close score |
| Inventory & Placement | `/inventory` | inventory, dealers | stock health, reorder priorities, substitute vehicles |
| Market Sentiment | `/sentiment` | (news) | news-driven demand signals and a written briefing |

**Standing project constraints** (they explain many decisions below):

- **Everything must stay free of cost.** Open-source and self-hosted tools only; paid AI scoring is opt-in and off by default.
- **Isolation between customers is the top security requirement.** It is enforced by the database, not just by application code.
- **Presentation is market-neutral.** Currency, language, region wording and units come from per-tenant settings, not code forks.

---

## 2. Tech stack, and why each piece

### 2.1 The stack at a glance

| Layer | Choice | Version notes |
|---|---|---|
| Language (backend) | Python | 3.11 in Docker (runs on newer locally) |
| HTTP API | FastAPI + Pydantic v2, served by Uvicorn | thin shell only |
| Database | PostgreSQL 16 | Row-Level Security is the isolation mechanism |
| ORM / SQL | SQLAlchemy 2 + psycopg2 | pandas `read_sql` for analytics |
| Authentication | GoTrue (open-source Supabase Auth), self-hosted | JWTs, HS256 shared secret |
| Background jobs | Redis + RQ (thread fallback with no Redis) | one queue, `ingest` |
| Analytics / ML | pandas, NumPy, scikit-learn, Prophet, XGBoost, SHAP | models trained per tenant |
| News | Google News RSS + offline scorer (paid LLM optional) | `defusedxml` for parsing |
| Web apps | Next.js 16 (App Router), React 19, TypeScript | two separate apps |
| UI kit | Tailwind CSS 4, shadcn/ui (Radix), lucide icons | our own design tokens |
| Client data | TanStack Query 5 | caching and polling |
| Charts / maps | Recharts (via shadcn charts), `d3-geo` for the map | SVG, theme-coloured |
| Theming, toasts | next-themes, sonner | light and dark |
| Containers | Docker + Docker Compose | non-root, read-only |
| Tests | pytest (Python), Vitest (web), Playwright used ad hoc | see section 14 |
| Quality / security scans | ruff, bandit, pip-audit, npm audit | run in CI |

### 2.2 Why these choices

**Postgres with Row-Level Security, one shared database.** The alternative was a database per tenant. We chose a shared schema
with a `tenant_id` on every business table because it means one schema to migrate and one connection pool at thousands of tenants,
while the *database itself* guarantees isolation: a query cannot return another tenant's rows even if application code forgets a
`WHERE`. Section 5 explains the mechanism. The cost is that every table and every code path must respect the tenant scope, which
the architecture tests and the request-scope design enforce.

**GoTrue (Supabase Auth), self-hosted, instead of writing auth.** Password storage, token issuing, refresh and rate limits are
security-critical and easy to get wrong. GoTrue is open source (fits "everything free"), runs as one container against the same
Postgres (its own `auth` schema), and is API-compatible with hosted Supabase, so moving to a hosted project later is an
environment-variable change. The tenant and role live in `app_metadata`, which users cannot edit (only the service key can).

**FastAPI as a thin shell in front of a services layer.** The web apps must never touch the database. FastAPI gives typed request
validation (Pydantic), dependency injection (used for authentication and tenant binding), automatic OpenAPI docs in development,
and good performance. Routers stay small: they authenticate, validate, call `backend.services`, and serialise.

**A layered backend with rules enforced by a test.** Business logic lives in pure Python packages that know nothing about HTTP.
That made it possible to replace the whole frontend (Streamlit to Next.js) without rewriting the logic. The layer rules are checked
by `tests/unit/test_architecture.py`, so they cannot erode silently.

**Next.js + React + TypeScript for the web apps (replacing Streamlit).** The first UI was Streamlit. It was quick to build but
held sessions in server memory (a page reload signed you out), gave limited control over design, and was hard to make look
professional. Next.js gave httpOnly cookie sessions, a real component model, proper light/dark theming, and a design system.
The Streamlit apps were **retired** once both Next apps reached parity (see git history if you need the old code).

**Two separate web apps instead of one with an admin route.** The operator console has power over every tenant. Keeping it a
separate app, on its own port, bound to localhost, with its own cookie names, makes it possible to keep it off the public
internet (reach it over a VPN or SSH tunnel) and impossible for a customer session to be mistaken for an operator one.

**shadcn/ui + Tailwind 4.** shadcn copies component source into the repo (no runtime dependency to lock us in) on top of Radix
primitives (accessible by default). Design tokens are CSS variables in `app/globals.css`, so light/dark themes and a consistent
"analyst desk" look come from one place.

**TanStack Query.** Every dashboard tab is a set of server queries: caching, background refetch, and polling (import progress) come
for free, and query keys make invalidation explicit.

**Recharts and `d3-geo`, no map service.** Charts are shadcn's Recharts wrappers. The Store Performance map is plain SVG drawn from
bundled boundary files, using only theme colours: no map tiles, no external calls, works offline, and follows light/dark mode.

**Redis + RQ for background work.** Imports and retraining take minutes and must not block a request. RQ is small, open source and
needs only Redis. With no `REDIS_URL` the same job function runs in a thread, so local development needs no extra service.

**Prophet, XGBoost, scikit-learn, SHAP.** Prophet handles daily sales with strong seasonality and external regressors; XGBoost
gives a strong tabular classifier for lead close; scikit-learn KMeans segments customers; SHAP explains individual lead scores.
All are free and run on CPU. Section 9 also records honest findings about their accuracy.

**Free sentiment.** News comes from Google News RSS (no key, no rate-limit trouble) and is scored by an offline rule-based scorer.
A paid LLM path exists but is off unless explicitly enabled.

**Docker Compose with hardened containers.** One command brings up the whole stack; every container runs as a non-root user with a
read-only filesystem, all capabilities dropped, and ports bound to `127.0.0.1` only (section 13).

### 2.3 Decisions that are recorded elsewhere

Design rationale for individual passes (comparative analytics, customer intelligence, sentiment, dealer positioning) is in
`docs/next-pass-*.md` and `docs/changelog/`. The research that led to the current forecasting and demo-data work is in
`docs/research/`.

---

## 3. System architecture

### 3.1 The shape of the system

```
 browser ──► customer dashboard  (Next.js, web/,        :3000) ──/api──┐
 browser ──► admin console       (Next.js, web-admin/,  :3002) ──/api──┤
                                                                       ▼
                                          FastAPI  (backend/api, port 8000, NOT published)
                                                                       │  calls only
                                                                       ▼
                                          backend.services  ◄── the only door into the backend
                                                                       │
        ┌────────────┬──────────────┬───────────────┬─────────────────┼───────────────┐
        ▼            ▼              ▼               ▼                 ▼               ▼
   repositories  analytics / ml  ingestion       tenancy          sentiment         auth client
        │            │              │               │                 │               │
        └──────► backend.db (engines, RLS, ORM) ◄───┘                 │               ▼
                        │                                             │        GoTrue (auth)
                   PostgreSQL 16                          Google News RSS (public)
        Redis ◄── RQ worker (imports, retraining), same image as the API
```

Key points:

- The browser only ever talks to **its own Next.js origin**. Next proxies `/api/*` to FastAPI (`rewrites` in `next.config.ts`),
  so the API needs no CORS and its cookies are first-party.
- The API container is **not published**. Only the two Next containers (and the database, auth and Redis on localhost) are reachable.
- The **worker** runs the same image as the API with a different command (`rq worker ingest`).

### 3.2 The backend layers

`backend/` is split into packages with a strict rule: **a package may import only from its own layer or a lower one.**
`tests/unit/test_architecture.py` fails the build if this is broken, if a new package is not classified, or if the API imports
anything but `backend.services` (and `core`/`api`) or a forbidden third-party module (SQLAlchemy, psycopg2, redis, rq, jwt).

| # | Package | Responsibility |
|---|---|---|
| 0 | `core` | config, request scope, formatting, cache, errors, logging, security primitives |
| 1 | `db` | engines, sessions, row-level security, ORM models |
| 2 | `repositories`, `auth` | SQL by domain (sales, dealers, customers, inventory, catalog); the GoTrue client |
| 3 | `analytics` | decision engine, YoY attribution, what-if model, inventory health, retention, benchmarks |
| 4 | `sentiment` | news intake, offline scoring, group briefing |
| 5 | `ml` | forecasting, segmentation, lead scoring, vehicle placement, backtesting, signed artifacts |
| 6 | `ingestion` | field catalog, mapping engine, transform + load, background jobs |
| 7 | `tenancy` | provisioning, capabilities, settings validation, audit, account summary, CSV loader |
| 8 | `services` | application services: the API's only surface into the backend |
| 9 | `api` | HTTP shell: cookie sessions, tenant binding, JSON; calls only `services` |

`backend/cli.py` is an entry point and may use anything.

### 3.3 Repository layout

```
backend/                 all logic (layers above)
web/                     customer dashboard (Next.js)
web-admin/               operator console (Next.js)
deploy/postgres/         database bootstrap (roles, default-deny)
scripts/                 data generators, dataset builder, backtest, map builder
data/public/             real public reference series (FRED) used for backtests and demo data
docs/                    architecture, security, operations, this guide, research/
requirements/            base.txt (ranges), lock.txt (pinned, audited), dev.txt
tests/                   unit/, integration/, e2e/
docker-compose.yml, Dockerfile   the stack and the Python image
.github/workflows/ci.yml         CI
Accounts-Datasets/       (untracked) upload-ready CSV sets for the demo accounts
```

### 3.4 Ports and services (local stack)

| Service | Port | Published? | Purpose |
|---|---|---|---|
| `frontend` | 3000 | localhost only | customer dashboard |
| `admin-frontend` | 3002 | localhost only | operator console |
| `api` | 8000 | no | FastAPI |
| `worker` | none | no | RQ worker |
| `db` | 5432 | localhost only | Postgres |
| `auth` | 9999 | localhost only | GoTrue |
| `redis` | 6379 | localhost only | queue and shared throttle |

---

## 4. The backend, layer by layer

### 4.1 `core` (layer 0)

- **`config.py`** is the **only** place configuration is read (`os.getenv` is used nowhere else). `get_settings()` builds a frozen
  `Settings` from environment variables (a local `.env` is loaded in development). With `ENVIRONMENT=production`,
  `assert_production_ready()` makes the process **refuse to start** if it finds development passwords, identical app and owner DB
  URLs, a JWT secret under 32 characters or a development default, non-https auth URLs (except private hostnames), or a Redis URL without a
  password. `model_signing_key` is derived from the JWT secret so there is nothing extra to manage.
- **`request_context.py`** holds the per-request scope in `ContextVar`s: the tenant, the tenant profile (currency, language, region
  label, country, news edition), the language, and the acting operator. `tenant_context(tenant_id)` scopes work to one tenant (used
  by workers, operator actions, scripts and tests); `bind_request(profile, language)` scopes one signed-in request;
  `clear_request()` drops it. With no scope set, Postgres returns **zero rows** (fail closed).
- **`cache.py`**: `@tenant_cache(ttl, maxsize)`. The tenant id is *always* part of the key (a cache shared across tenants would be a
  data leak), arguments starting with `_` are left out of the key, and values are deep-copied in and out.
- **`security.py`**: `LoginThrottle` (in-process) and `RedisLoginThrottle` (shared across instances, falls back to in-process if Redis
  is down), plus `validate_password`.
- **`errors.py`**: `AppError` (safe to show: `str(e)` is user-facing), with `AuthError`, `IngestError`, `InvalidSetting`; and
  `TenantNotSet` (a programming error). Anything else is treated as unexpected and never shown.
- **`formatting.py`, `log.py`**: number/currency/date formatting and logging.

### 4.2 `db` (layer 1)

- **`connection.py`** builds **two engines**: the **app engine** (restricted `predictax_app` role, RLS enforced) and the **admin
  engine** (table owner, used only for schema changes, tenant provisioning and the audit trail). A SQLAlchemy `begin` event on the
  app engine runs `set_config('app.current_tenant_id', <id>, true)` at the start of every transaction (transaction-local, so it is
  safe with pooled connections).
- **`rls.py`** applies row-level security to every table (section 5).
- **`models/`**: `tenant.py` (Tenant, ColumnMapping, IngestJob), `business.py` (Customer, Vehicle, Dealer, Sale, Inventory,
  ExternalFactor), `sentiment.py` (NewsArticle, SentimentSignal, DailySentimentSummary), `audit.py` (AuditEvent).

### 4.3 `repositories` and `auth` (layer 2)

Repositories are plain functions that run SQL for one domain and return DataFrames or dicts. Shared filter logic is in
`_filters.py`. They never take a session from a caller; they use the tenant-scoped session, so RLS applies. `auth/client.py`
talks to GoTrue: sign-in, refresh, JWT verification, and the service-key admin calls that create and delete users.

### 4.4 `analytics` (layer 3)

Business calculations, presentation-free (labels are stable keys, not display text): `decision_engine.py` (ranked "plays"),
`yoy_attribution.py`, `what_if.py`, `inventory_health.py`, `retention.py`, `benchmarks.py`. Details in section 9.

### 4.5 `sentiment` (layer 4)

Fetch news, score it, aggregate daily signals, and build the group briefing (section 10).

### 4.6 `ml` (layer 5)

`demand_forecast.py`, `forecast_report.py`, `customer_segmentation.py`, `lead_scoring.py`, `vehicle_placement.py`, `backtest.py`,
`training.py` (trains a tenant's models), and `artifacts.py` (signed model storage). Details in section 9.

### 4.7 `ingestion` (layer 6)

`catalog.py` (the field catalog), `mapping.py` (column mapping engine), `pipeline.py` (transform and load), `jobs.py` (job
lifecycle). Section 8 walks through them.

### 4.8 `tenancy` (layer 7)

`provision.py` (create, configure, suspend, **delete** tenants and logins), `capabilities.py` (which tabs a tenant's data supports),
`settings.py` (validation of tenant settings), `audit.py` (append-only operator trail), `summary.py` (account counts and model
status), `loader.py` (load a folder of CSVs; used by the CLI and scripts).

### 4.9 `services` (layer 8)

The API's only door. Each module is a small, framework-free façade: `identity`, `workspace`, `overview`, `forecasting`,
`comparison`, `stores`, `customers`, `inventory`, `sentiment`, `accounts`, `imports`. Services compose repositories, analytics and
ML, and return plain data (dicts, DataFrames, dataclasses), **never** a session or ORM object.

### 4.10 `api` (layer 9)

- `app.py` is the application factory: middleware (CSRF header check, hardening headers), exception handlers, router registration.
- `deps.py` provides `CurrentCustomer`, `CurrentOperator` and `Filters` dependencies (the global dashboard filters).
- `cookies.py` sets and reads the session cookies (separate names for customers and operators).
- `serialize.py` (`to_jsonable`) converts DataFrames, dates and NaN into JSON-safe values.
- `routers/`: customer routes (`auth`, `workspace`, `overview`, `forecasting`, `comparison`, `regional`, `customers`,
  `inventory`, `sentiment`) and operator routes (`admin_auth`, `admin_accounts`, `admin_imports`, `admin_audit`).

---

## 5. Multi-tenancy and the database

### 5.1 The mechanism

One shared PostgreSQL database. Every business table has a `tenant_id`. Row-Level Security (RLS) policies compare it with the tenant
the current transaction is pinned to:

1. After login, the auth server's signed token carries a `tenant_id` claim (in `app_metadata`, settable only by the service key).
2. The API binds that tenant into the request's `ContextVar` scope (`deps.customer`).
3. Every transaction on the app engine runs `set_config('app.current_tenant_id', <id>, true)` first.
4. Postgres adds `tenant_id = current tenant` to every read and checks it on every write, whatever the SQL says (policy
   `tenant_isolation`, `USING` and `WITH CHECK`, expression `NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`).
5. With no tenant bound the setting is empty, the expression is `NULL`, and queries return **zero rows** (fail closed).

### 5.2 Roles and privileges

- **`predictax_app`** (the API and worker): not a superuser, no `BYPASSRLS`, cannot create objects, has *explicit* grants only.
- **`predictax_owner`** (table owner): used by the admin engine for `init-db`, provisioning and the audit trail. `FORCE ROW LEVEL SECURITY`
  is on for tenant tables, so **even the owner is subject to RLS** on data tables.
- The two roles **must differ** (production guard).
- **Default-deny:** any table with no `tenant_id` (for example `audit_events`, and future tables) gets `REVOKE ALL` from the app role.
  The `tenants` table has `id` as its key, is readable by the app role but not forced, so provisioning by the owner works.

### 5.3 Schema notes

- Composite primary keys `(tenant_id, id)`; **foreign-key child indexes are required** (parent deletes were quadratic without them).
- Market-neutral columns: no currency in any column name, `region` (not "state" or "emirate"), `credit_score`, `tax_amount`,
  metric units, and a per-row `extras` JSON for source columns with no canonical home.
- `Text` rather than `varchar` limits; the field catalog (`ingestion/catalog.py`) is the single source of truth and a test keeps it
  in sync with the ORM models.
- `tenants.config` (JSON) holds presentation settings: currency, symbol and position, language, region label, country, news edition.
- `column_mappings` remembers each tenant's confirmed column mapping per table; `ingest_jobs` tracks imports and retrains.

### 5.4 Tenant-keyed everything else

- **Caches** are keyed by tenant (`tenant_cache`).
- **Files:** uploads under `<UPLOAD_DIR>/<tenant_id>/<job_id>/`, models under `<MODEL_DIR>/<kind>/<tenant_id>/`.
- **News** is fetched once per country/language edition and shared, because it is public (each tenant still stores its own rows;
  see known limitations).

### 5.5 Schema management

There is no migration tool yet. `python -m backend.cli init-db` creates tables and (re)applies RLS and grants; it is idempotent.
`reset-db --yes` drops everything (development only). **Never run DDL tests (`init_all_tables`) while other database work is
running; they deadlock.**

---

## 6. Identity, sessions and access

### 6.1 Two kinds of login, strictly apart

- A **customer** token carries a `tenant_id`; the customer app accepts only tokens that have one.
- An **operator** token has `role = platform_admin` and **no** tenant; the admin console accepts only those.
- A token of one kind presented to the other is refused **with the same message as a wrong password**.

### 6.2 Token verification

`auth_client.verify_access_token` validates the signature (HS256 shared secret, or JWKS for asymmetric projects), the audience
(`authenticated`), and **requires** `exp`, `sub` and `aud` claims (PyJWT does not insist on an expiry by default). Tenant and role
come from `app_metadata`; editing `user_metadata` changes nothing (tested).

### 6.3 Cookies

Tokens live **only** in httpOnly cookies, so page scripts (and therefore any XSS) cannot read them.

| | Customer | Operator |
|---|---|---|
| Access cookie | `px_access` (path `/`) | `px_admin_access` (path `/`) |
| Refresh cookie | `px_refresh` (path `/api/auth`) | `px_admin_refresh` (path `/api/admin/auth`) |
| Attributes | `HttpOnly`, `SameSite=Strict`, `Secure` in production; refresh lasts 7 days | same |

The separate names and separate FastAPI dependencies (`deps.customer` vs `deps.operator`) mean a browser with both apps open can never
have one session mistaken for the other.

### 6.4 Refresh and expiry

The web client (`lib/api.ts`) treats a `401` on a normal request as "access token expired": it calls the refresh endpoint **once**
(deduplicated across concurrent requests) and retries. Every API request verifies the token and then confirms the tenant is still active; that lookup is remembered for about a minute (`_TENANT_RECHECK_S`), so a **suspended account is locked out within about a minute** without a database query on every request. The operator console also signs an operator out after **30 minutes idle** (a client-side timer in
`web-admin/src/lib/idle.ts`).

### 6.5 CSRF

Every non-`GET`/`HEAD`/`OPTIONS` request must carry `X-Requested-With: predictax`, enforced by middleware in `api/app.py`
(a cross-site form cannot add a custom header). This sits on top of `SameSite=Strict`.

### 6.6 Throttling and passwords

- Sign-in is throttled **per account** on the server: **5 failures lock the account for 15 minutes**. The counters are shared across
  instances through Redis when `REDIS_URL` is set (fixed window), with an in-process fallback if Redis is unreachable. The auth
  server rate-limits too.
- Passwords a person chooses must be at least 10 characters, not trivially repetitive, and not in a common-password list. Generated
  passwords are long and random and are shown **once**.

### 6.7 Operator powers and audit

Operators can create, configure, suspend and **delete** accounts, add logins, reset passwords, import data and retrain. Every
operator action is written to `audit_events` (actor, action, target tenant, outcome, non-secret detail). The table is **append-only**
(database triggers reject `UPDATE`, `DELETE` and `TRUNCATE`) and unreadable by the app role.

---

## 7. Life of a request

### 7.1 A customer request (for example the Store Performance tab)

1. The browser calls `GET /api/regional/scorecard` on the Next.js origin with the query string of the global filters.
2. Next proxies it to `http://api:8000/api/regional/scorecard` (a `rewrite`).
3. FastAPI's `customer` dependency reads `px_access`, verifies the JWT in a thread, loads the tenant's profile, checks the tenant is
   active, and **binds the tenant** in the request context (an async dependency, so the binding is in the request's own context
   and is copied into the threadpool for the sync endpoint that follows).
4. The `Filters` dependency reads the filter query parameters (dates default to the tenant's whole sales history).
5. The router calls `backend.services.stores.scorecard(filters)`.
6. The service calls repositories; each opens a session on the app engine. The `begin` event pins the transaction to the tenant, and
   Postgres applies RLS.
7. The service returns a DataFrame/dict; the router passes it through `to_jsonable`.
8. Middleware adds `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`.
9. The dependency's `finally` runs `clear_request()`, so nothing leaks to the next request on the same worker thread.
10. In the browser, TanStack Query caches the result; the page component renders it. Currency and number formatting is done client
    side from the tenant profile the API returned (the API returns raw numbers).

### 7.2 An operator request

Same shape, but the `operator` dependency reads `px_admin_access`, verifies an operator token, and calls `bind_actor(email)` so the
audit trail attributes the action. There is no tenant binding: operator services take an explicit tenant id and use
`tenant_context(tenant_id)` when they must read a tenant's data.

### 7.3 Error handling

`AuthError` becomes `401`; other `AppError`s become `400` with their safe message; **any other exception** is logged with a short
reference id and returned as `500 "Something went wrong on our side."` plus that reference. Stack traces and exception text
**never** reach the browser.

---

## 8. Data flow: getting a customer's data in

### 8.1 The field catalog

`backend/ingestion/catalog.py` is the single source of truth for what a customer can upload: six tables
(`vehicles`, `dealers`, `customers`, `external_factors`, `sales`, `inventory`), each with fields that carry a kind
(`str/int/float/bool/date`), whether they are required, a default for gaps, **aliases** (synonyms), **converted aliases**
(source names that imply a unit conversion, such as `mpg` or `horsepower`), and a distance flag. **Only the sales file is required;**
optional files unlock optional tabs. Everything is stored in neutral names and metric units.

### 8.2 The mapping engine

`mapping.propose_mapping(table, columns)` decides, for each canonical field, which source column feeds it, in this order:

1. **exact**: the source name is the canonical name (currency tokens such as `_eur`, `_usd` are ignored);
2. **converted**: the name implies a unit conversion (`mpg` to l/100km, `range_miles`, `horsepower`...);
3. **alias**: a known synonym (`state`, `emirate` to `region`; `zip_code` to `postal_code`);
4. **fuzzy**: a close spelling. **Never applied automatically**; the operator must confirm it.

A source column can feed at most one field; leftovers are kept in `extras`. If a tenant has imported before and the saved mapping still fits
the new file, it is offered instead.

### 8.3 The import, step by step

1. **Upload** (admin console, Import data tab). Each CSV is posted to `POST /api/admin/accounts/{slug}/imports/{job_id}/files/{table}`
   (multipart). The job id is a UUID generated in the browser and reused for the whole wizard session. The file is stored under
   `<UPLOAD_DIR>/<tenant_id>/<job_id>/<table>.csv`, subject to `MAX_UPLOAD_MB` (500). The Next proxy is configured to allow bodies up to 520 MB
   (its default is 10 MB, which once broke large uploads).
2. **Mapping proposal.** `GET .../{table}/mapping` reads the header and returns the columns, the proposal with a confidence per field,
   missing required fields, whether imperial units were hinted, and any compatible saved mapping. The wizard shows an editable grid.
3. **Dry run** (optional). `POST .../{table}/dry-run` transforms the first 3,000 rows and reports rows usable, values that could not be
   read, and warnings, changing nothing.
4. **Start.** `POST .../start` builds the job options (files, mappings, units, date order, decimal separator, replace or add, train)
   and creates an `ingest_jobs` row with status `queued`, then enqueues it: to the Redis/RQ `ingest` queue if `REDIS_URL` is set
   (`job_timeout` one hour), otherwise a background thread. The API returns immediately.
5. **The worker** (`jobs.process_job`) re-scopes itself to the tenant and runs `pipeline.run_ingest`:
   - reads each CSV **as text** (limits: 500 columns, 5 million rows) and applies `transform_table`: map, convert units, coerce types
     (dates, numbers with `.` or `,` decimals, booleans), fill defaults only in columns the customer supplied, validate required
     fields, derive missing dealers and vehicles from the sales file, drop duplicates on the natural key, and collect an `extras` JSON;
   - loads via `load_frames`: `COPY` into a temporary table, then `INSERT ... SELECT`, all inside **one tenant-scoped transaction**
     so RLS checks every row. **Replace** mode clears the account's data first. **Any failure loads nothing.**
6. **Remember the mapping** (`column_mappings`), then **train the models** (section 9; failures become notes, they do not fail the import).
7. **Progress.** The worker updates the job row's `stage`, `progress` and `status`. The wizard polls
   `GET /api/admin/accounts/{slug}/jobs/{job_id}` every 1.5 seconds and shows a progress bar.
8. **Done.** `POST .../done` clears the capabilities cache so the new data (and any newly unlocked tabs) show immediately.

Retraining without importing is `POST /api/admin/accounts/{slug}/retrain`, which creates a `train_only` job. To retrain every account
inside the stack: `docker compose exec worker python -m backend.cli train --all` (models live in the container volume, so run it there).

### 8.4 What "capabilities" do

`tenancy/capabilities.py` inspects which tables have data (cached for 60 seconds) and `TAB_REQUIRES` decides which tabs to offer. A
tab an account cannot populate is **hidden, not shown broken**. A brand-new account with no sales sees "Your account is being set up".

### 8.5 From database to screen

The tab services read the tenant's data with repositories, run analytics or models, and the API returns raw numbers. The web app formats
them using the tenant profile. Expensive results (forecasts, comparisons, news) are cached per tenant for minutes (`tenant_cache`).

---

## 9. Analytics and machine learning

Models are trained **per tenant on that tenant's own data** and saved as HMAC-signed files (section 12) under
`<MODEL_DIR>/<kind>/<tenant_id>/`. `ml/training.py:train_tenant_models` trains segmentation and lead-close; the forecast is **not** pre-trained.

### 9.1 Demand forecasting

- `demand_forecast.train_prophet_model` aggregates daily sales for the chosen filters, merges the tenant's monthly external factors
  (fuel price, auto-loan APR, incentive spend, inventory days' supply, quarter-end flag, optional news-sentiment signals) as Prophet
  regressors, fits, and forecasts.
- `forecast_report.py` turns that into whole calendar months with a confidence range (80% level, shrunk toward square-root scaling because
  daily errors partly cancel), seasonality, and the effect of any **what-if** market levers.
- **What-if** (`analytics/what_if.py`): the levers are crude price, petrol and diesel price, and loan APR; each maps to a real external-factor
  column, and `net_response_pct` combines active levers into a % shift in demand versus the recent baseline (with a supply-drag term).
- The forecast is computed on request and cached about 10 minutes.

### 9.2 Customer segmentation

KMeans (5 clusters) on age, income, credit score, years at address, number of past purchases, recency and average deal value. Labels:
High-Value / Prime, Core Mainstream, Value Buyers, Loyal Repeat, Lapsed / At-Risk. **Nationality and gender are deliberately not model
features** (fairness); nationality is shown descriptively only.

### 9.3 Lead close score

XGBoost classifier for "will this test drive convert" from customer demographics, deal parameters and channel. Details a developer must know:

- **Not features, on purpose:** `gender`, `nationality` (fairness) and `financing_type` (it is agreed late in the process and leaks the outcome).
- **Validation before training** (`training_problem`): needs at least 100 sales linked to customers and at least 10 won and 10 lost test drives; otherwise
  it records a specific reason instead of a generic failure.
- **Per-account status** (`lead_status` artifact): `not_trained`, `trained` (rows, holdout accuracy and AUC, feature coverage, missing features,
  `weak` if AUC is under 0.60) or `cannot_train` (with the reason). The Lead Close Score tab shows the reason, hides inputs the account has no
  data for, and warns when the model ranks barely better than chance.
- A **failed retrain removes the old model** so stale scores never run on new data; a failed prediction raises an error rather than returning a
  made-up 50%.
- Individual scores are explained with SHAP (with a heuristic fallback).

### 9.4 Vehicle placement (substitutes)

`vehicle_placement.py` recommends alternatives to a vehicle using a similarity that combines category and fuel affinity matrices, price,
location and availability, plus a business-priority score.

### 9.5 Decision engine, retention and inventory

- `decision_engine.generate_plays` returns ranked `Play` objects (allocation, targets, margin, aged inventory, F&I, velocity, category
  momentum) with an impact amount, horizon and confidence; rank is impact x confidence weight.
- `retention.action_queue` lists customers to contact now (lease maturing, overdue on their own cadence, lapsed high-value, churn-risk spike).
- `inventory_health` computes stock KPIs, reorder priorities and aged-stock actions.
- `yoy_attribution` decomposes year-on-year change into what a group controls versus what the market handed it.

### 9.6 Backtesting and what it found

`ml/backtest.py` is a rolling-origin backtest on a monthly series with seasonal baselines. `scripts/backtest_public_data.py` ran it on
real US market series. Findings (details in `docs/research/forecast-backtest-findings.md`):

- "Same month last year" is a hard baseline to beat (about 9 to 14% error at 1 to 12 months).
- The **current all-history Prophet setup loses to that baseline in steady markets**; a 10-year-window variant is competitive and much better in shocks.
- Prophet's **95% band covers only about 65 to 74%** of outcomes at 3 to 12 months.
- The built-in "accuracy" number (1 minus MAE over one 30-day daily holdout, using true future regressors) is flattering and should not be quoted.
- **Recommended, not yet built:** choose the best method per account by backtesting on its own history, use empirical intervals, and show measured accuracy.

---

## 10. Market sentiment

- **Fetch:** Google News RSS (primary; GDELT is the fallback) for the tenant's news edition (language, country, and the country name from its settings), with English and German
  query packs. Fetches are cached per edition, so the cost is per edition, not per tenant. XML is parsed with `defusedxml`.
  Google News RSS is the **primary** source; if it fails the pipeline falls back to GDELT, whose free API rate-limits heavily. `gdelt_fetcher.py` also supplies shared helpers and query definitions that the RSS path reuses.
- **Score:** an **offline** rule-based scorer produces sentiment, impact, affected vehicle category, demand direction and estimated demand change.
  A paid LLM path (`grok_analyzer.py`) runs only if `ALLOW_PAID_SENTIMENT` is set and a key is present.
- **Aggregate:** `DailySentimentSummary` stores one row per date and category; these can also feed the forecast as regressors.
- **Briefing:** `group_briefing.py` builds a cross-module "read" (executive summary, demand outlook, store performance, customers, inventory,
  sentiment) from a template, or from the LLM if enabled.
- **Safety:** news is public but attacker-influenceable text. Links must be plain `http(s)`; everything is escaped; scoring is offline by default.

---

## 11. The two web apps

Both are Next.js 16 (App Router), React 19, TypeScript, Tailwind 4, shadcn/ui. They share conventions but are separate builds.

### 11.1 Customer dashboard (`web/`)

```
src/app/            routes: login, and (app)/ for the seven tabs; globals.css holds design tokens (light + dark)
src/components/     ui/ (shadcn primitives), layout/ (shell, sidebar, filters), data/ (Section, MetricStrip, Insight, DataTable, states),
                    charts/ (ChartFrame, RegionMap, tooltips), login/
src/features/<tab>/ one folder per dashboard
src/lib/            api.ts (client), session.tsx (profile + formatting), filters.tsx (filters in the URL), i18n.ts, format.ts, query.ts, region-map.ts
src/i18n/           en/de JSON (extra.*.json for tab strings); a test enforces every used key exists in both languages
src/data/regions/   boundary files for the Store Performance map
```

- **Data access:** `lib/api.ts` is the **only** module that talks to the backend. It adds the CSRF header, retries once after a refresh on `401`, and
  turns failures into `ApiError`. Each tab uses `useDashboardQuery(...)` (TanStack Query) so filters in the URL change the query key.
- **Presentation:** currency, separators and language come from the tenant profile (`useMe`); the API returns raw numbers. Translations live in JSON.
- **Design language ("analyst desk"):** hairline-divided sections instead of boxed cards (`Section`, `Panel`), a connected KPI band (`MetricStrip`),
  `Insight` rows instead of alert boxes, `ChartFrame` (headline as the conclusion, export CSV, expand), brand-tinted neutral tokens, Manrope headings
  and Hanken Grotesk body. **Chart types are unchanged unless the change adds value.** The forecast grammar is a blue-to-green line with an "X" at the
  actual-to-forecast hand-over, echoing the logo.
- **Store Performance map:** `components/charts/region-map.tsx` draws an SVG map with `d3-geo` from `src/data/regions/{US,DE,AE}.json` (Natural Earth,
  public domain, simplified by `scripts/build_region_maps.py`). Bubble size is units, colour is pace to target, region shade is share of units, all in theme
  colours. The country is picked by matching the rooftops' region names (with alias spellings); an unknown country falls back to plain positions.
  Polygons must be wound **clockwise** for `d3-geo` (a test guards this).
- **Security headers:** a CSP, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and HSTS in production (set in `next.config.ts`).
- **Tests:** Vitest for formatting, translations, URL safety and the map logic.

### 11.2 Operator console (`web-admin/`)

- Same stack and design language, English only, no charts, no Recharts. Its own port (3002), its own cookies, its own API surface (`/api/admin/*`).
- **Screens:** accounts list and create (with generated credentials shown once), account detail with tabs: **Import data** (the upload, mapping, dry-run and job
  wizard), **History & models** (retrain and job history), **Logins**, **Settings**, **Access** (suspend/reactivate and **delete account**), and the **Audit log**.
- **One-time credentials:** generated passwords are handed to the next page once via `sessionStorage` (`lib/flash.ts`) and never persisted.
- **Idle sign-out:** 30 minutes (`lib/idle.ts`).
- **Upload size:** `experimental.proxyClientMaxBodySize` is set to 520 MB in `next.config.ts` so large CSVs pass the proxy.

---

## 12. Security measures

This section lists the controls in the order an attacker would meet them. [security.md](security.md) has the threat table and the production checklist.

### 12.1 Configuration and secrets

- All configuration comes from environment variables read in one module; **`.env` is git-ignored and must never be committed.** (Earlier history once held
  real API keys; treat those as exposed and rotate them.)
- **Production refuses to start** with development secrets, weak JWT secrets, identical app/owner roles, non-https auth URLs, or a passwordless Redis.
- Secrets are provided through the platform's secret store in production, never baked into images.

### 12.2 Network and containers

- Every published port is bound to `127.0.0.1`; the API is not published at all. The admin console must be reached over a VPN or SSH tunnel.
- Containers run as a **non-root user (uid 10001)**, with a **read-only filesystem**, `cap_drop: ALL`, `no-new-privileges`, and tmpfs for scratch space.
- Redis requires a password; images are tag-pinned; Python dependencies are pinned in `requirements/lock.txt`.

### 12.3 Authentication and sessions

Section 6 in full: separate customer and operator identities, verified JWTs with required claims, httpOnly + SameSite=Strict cookies (Secure in production),
re-verification on refresh, suspension enforced within about a minute, a 30-minute operator idle timeout, shared login throttling, password policy, and
tenant/role taken from claims users cannot edit.

### 12.4 Request protection

- **CSRF:** the mandatory `X-Requested-With: predictax` header on every state-changing request.
- **No CORS:** the browser talks only to its own origin.
- **Validation:** Pydantic models with strict patterns, ranges and `Literal` types on every request body and path parameter (slugs, UUID job ids, table names).
- **Errors:** safe messages only; unexpected errors are logged with a reference id, never shown.
- **Response headers:** `Cache-Control: no-store` on all API responses, `nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`; the Next apps add a CSP and HSTS.

### 12.5 Data isolation

Section 5: RLS with `USING` and `WITH CHECK` on every tenant table, `FORCE`d so even the owner is subject to it; a restricted app role with explicit grants;
default-deny for non-tenant tables; a fail-closed empty scope; tenant-keyed caches, model directories and upload directories; and tests proving that identical
ids in two tenants stay separate, that unscoped reads return nothing, that cross-tenant writes are rejected, that pooled connections do not carry a tenant to the
next borrower, and that caches never cross tenants. The API and services can never import the ORM or SQLAlchemy (architecture test).

### 12.6 Uploads and parsing

- File size limit (`MAX_UPLOAD_MB`, default 500); row and column limits (5 million rows, 500 columns); CSVs are read as **text**, never executed or evaluated.
- The retention export defuses spreadsheet formula injection (cells starting with `=`, `+`, `-`, `@` are prefixed).
- News XML is parsed with `defusedxml` (no entity expansion or external entities); news links must be plain `http(s)`.
- SQL is parameterised; the only interpolated identifiers come from our own model metadata.

### 12.7 Model files

Saved models are **pickles, which run code when loaded**. Every artifact is stored as `<HMAC-SHA256 hex>\n<pickle bytes>`, signed with a key derived from the JWT secret,
and the signature is verified **before** unpickling. An unsigned, altered or differently-signed file is refused, never executed. Writes are atomic file replaces.
**Rotating the JWT secret invalidates every saved model; retrain all accounts afterwards.**

### 12.8 Audit trail

Operator sign-ins, account changes, imports, retrains, resets and deletions are recorded in `audit_events`: append-only (triggers block update, delete and truncate),
unreadable by the app role, and never containing secrets.

### 12.9 Supply chain and code scanning

`ruff` (including its security rules), `bandit` (medium and above must be clean), `pip-audit` on the pinned lock file, and `npm audit` (high and above) run in CI.
Only free, actively maintained libraries are used.

### 12.10 Fairness and data protection choices

Gender and nationality are not features of any per-person score; financing type is excluded from lead scoring to avoid leakage. Demo and sample data are synthetic;
if real customer data is ever handled, anonymise names and contact details before import (the platform does not need them to forecast) and agree retention and deletion.
Account deletion is real: it removes logins, rows, uploads and models.

### 12.11 Known security limitations

- Operators have a single role and no second factor yet.
- The tenant cache is per process (login throttling is shared via Redis).
- Audit records can be removed only by someone able to drop the trigger as the database owner, so restrict that role.
- Production hosting, TLS termination, SMTP for password-reset email and backups are not yet designed (section 18).

---

## 13. Infrastructure and deployment

### 13.1 Docker Compose services

| Service | Image / build | Notes |
|---|---|---|
| `db` | `postgres:16-alpine` | bootstrap script creates roles and default-deny grants |
| `auth` | `supabase/gotrue:v2.170.0` | sign-up disabled; email autoconfirm on for development (turn off in production and configure SMTP) |
| `redis` | `redis:7-alpine` | password, append-only file |
| `api` | Python image | `uvicorn backend.api.app:app`, health check `/api/health` |
| `worker` | Python image | `rq worker ingest`; no HTTP server |
| `frontend` | `./web` | Next standalone server, proxies `/api` to `http://api:8000` (baked at build) |
| `admin-frontend` | `./web-admin` | same, port 3002 |

Volumes: `pgdata`, `redisdata`, `uploads` (`/data/uploads`), `models` (`/app/models`).

### 13.2 The Python image

Multi-stage: a builder installs `requirements/lock.txt` into a virtualenv; the runtime stage has no compilers, runs as uid 10001, and defaults to
`ENVIRONMENT=production` (Compose overrides this for local use). Default command is the API.

### 13.3 Environment variables

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` or `production` (production enables the startup guard) |
| `DATABASE_URL` / `ADMIN_DATABASE_URL` | app role (RLS enforced) / owner role (schema, provisioning, audit); must differ |
| `APP_DB_PASSWORD`, `OWNER_DB_PASSWORD`, `AUTH_DB_PASSWORD` | database passwords Compose sets on first start |
| `AUTH_BASE_URL` | GoTrue URL (or set `SUPABASE_URL` + keys for hosted Supabase) |
| `SUPABASE_JWT_SECRET` | signs and verifies tokens and (derived) model files; at least 32 random characters in production |
| `REDIS_URL`, `REDIS_PASSWORD` | queue and shared throttle; unset means threads |
| `UPLOAD_DIR`, `MODEL_DIR`, `MAX_UPLOAD_MB` | file locations and the upload limit |
| `XAI_API_KEY`, `ALLOW_PAID_SENTIMENT` | optional paid sentiment scoring (off by default) |
| `LOG_LEVEL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | tuning |

### 13.4 Production checklist (summary)

Set `ENVIRONMENT=production` and generate real secrets; TLS-terminating reverse proxy in front of the customer dashboard; keep the admin console private;
configure SMTP and turn off email autoconfirm; back up Postgres and the `uploads` and `models` volumes; rotate any key that was ever committed.
The full list is in [security.md](security.md); runbook tasks (onboarding, retraining, suspension, backups, troubleshooting) are in [operations.md](operations.md).

### 13.5 Scaling notes

Scale imports with more workers (`--scale worker=3`). The API and both web apps are stateless (sessions are cookies with signed tokens), so they scale horizontally
behind a load balancer. Put PgBouncer in transaction-pooling mode in front of Postgres if connections become the limit: tenant scoping is transaction-local, so it is
compatible.

---

## 14. Testing and quality gates

### 14.1 Python (pytest)

| Marker / folder | Needs | What it covers |
|---|---|---|
| `tests/unit` (`-m unit`) | nothing | architecture rules, config guard, mapping engine, catalog-vs-model sync, formatting, throttle, artifacts, tokens, backtest, lead readiness, dataset export |
| `tests/integration` | Postgres | tenant isolation, ingestion, jobs, audit and limits |
| `tests/e2e` | Postgres, auth, (Redis) | real logins and the full HTTP API: admin accounts, imports, deletion, customer tabs, queue |

Tests skip themselves when a service they need is down. Useful commands:

```bash
pytest -m unit                            # no services needed
pytest -m "unit or integration"           # needs: docker compose up -d db
AUTH_BASE_URL=http://localhost:9999 pytest   # everything (needs db, auth, redis)
ruff check backend tests
bandit -r backend -ll
pip-audit -r requirements/lock.txt --no-deps --disable-pip
```

**Do not run two pytest processes against the same database at once** (DDL tests can deadlock).

### 14.2 Web (Vitest, lint, types, build)

```bash
cd web            # or web-admin
npm run lint && npm run typecheck && npm test && npm run build
```

### 14.3 CI (`.github/workflows/ci.yml`)

Three jobs on every push and pull request: **checks** (ruff, bandit, pip-audit, unit tests), **web** and **web-admin** (install, lint, typecheck, test, build, `npm audit`).

### 14.4 Browser verification

For UI changes, run the stack and look at it in a browser (Playwright was used ad hoc and is not a project dependency). Type checks and tests verify code, not that a
feature looks and behaves right.

---

## 15. Working locally

### 15.1 First-time setup

```bash
python -m venv venv && venv/Scripts/activate            # Windows; use `source venv/bin/activate` elsewhere
pip install -r requirements/dev.txt && pip install -e . --no-deps
cp .env.example .env

docker compose up -d db auth                            # Postgres + auth server
python -m backend.cli init-db                           # tables, row-level security, grants
python -m backend.cli create-operator --email you@example.com   # prints a generated password once
```

### 15.2 Run

```bash
docker compose up -d --build           # full stack: db, auth, redis, worker, api, both web apps
# or from source:
python -m uvicorn backend.api.app:app --reload --port 8000
(cd web && npm install && npm run dev)            # http://localhost:3000
(cd web-admin && npm install && npm run dev)      # http://localhost:3002
```

The Next apps read `API_URL` (default `http://localhost:8000`) to know where to proxy `/api`. In Docker it is baked in at image build time.
Working logins for local development are kept in the untracked `logincreds.txt` at the repository root; they are for local use only.

### 15.3 The CLI (`python -m backend.cli ...`)

`init-db`, `reset-db --yes` (dev only), `list`, `create-tenant`, `create-user`, `create-operator`, `set-config`, `load-csv --tenant <slug> --dir <folder>`,
`train --tenant <slug>` or `train --all`.

**Remember:** models are saved under `MODEL_DIR`. In Docker that is the `models` volume, so train inside a container (`docker compose exec worker ...`); training from
your own shell writes to a different folder that the containers never read.

### 15.4 Tips for this environment

- After changing code that runs in containers, rebuild the image (`docker compose build api frontend admin-frontend`) and `docker compose up -d`.
- On Windows, if a port misbehaves only from the host, look for a leftover local dev-server process holding it.
- Very long shell heredocs can fail; write files with an editor instead.

---

## 16. Recipes: common changes

**Add a field customers can upload.** Add it to the table tuple in `ingestion/catalog.py` (with kind, aliases, default), add the column to the ORM model in
`db/models/business.py`, run `init-db`, and the schema-sync test will tell you if they disagree. The mapping engine and import wizard pick it up automatically.

**Add an API endpoint.** Write the logic in a `backend/services/*.py` function (plain data in and out); add a router function that depends on `CurrentCustomer` and
`Filters` (or `CurrentOperator`), validates input with Pydantic, calls the service, and returns `to_jsonable(...)`. Register the router in `api/app.py`. The API must
import only `backend.services`, `backend.core` and `backend.api`.

**Add a dashboard tab.** Add the route under `web/src/app/(app)/`, a feature folder under `web/src/features/`, the tab key to `TABS` in `api/routers/workspace.py` and to
`TAB_REQUIRES` in `tenancy/capabilities.py`, navigation in `lib/nav.ts`, and strings in both `web/src/i18n/extra.en.json` and `extra.de.json` (a test enforces parity).

**Add a tenant setting.** Add a strict validation pattern in `tenancy/settings.py` (settings that reach markup are validated against patterns, not escaped), expose it through
`TenantProfile`, and add it to the operator Settings and create-account forms.

**Add a country to the Store Performance map.** Add it to `COUNTRIES` in `scripts/build_region_maps.py` (with any alternate spellings), run the script with the Natural Earth
file, add a loader in `region-map.tsx` and the code in `lib/region-map.ts`, and extend the tests.

**Add a model.** Put training and prediction in `backend/ml/`, store artifacts only through `artifacts.save_artifact`/`load_artifact` (signed), add it to
`ml/training.py:train_tenant_models`, and record why it cannot train in a status the UI can show.

**Retire or rename a package.** Classify new backend packages in `LAYERS` in `test_architecture.py` or the build fails.

---

## 17. Demo data and datasets

**Everything demo is synthetic.** No public dealer-level data exists, so demo tenants use generated records calibrated to real market figures. Never present them as a
customer's real data, and never quote forecast accuracy measured on them (the generator's own rules make the data easy to fit).

- **Generators:** `scripts/generate_de_data.py` (Germany), `generate_uae_data.py` (UAE), `generate_us_data.py` (America, with `us_market_data.py` for the catalog).
  Each models a 24-rooftop dealer group from January 2019 to August 2026.
- **Calibration:** Germany's yearly volume follows official KBA/Destatis totals; America's monthly volume follows the real US new-vehicle sales series; UAE's follows a published
  source for 2019 to 2022 (2023 onward is low confidence). Real macro series (FRED snapshots in `data/public/`) feed the external-factors tables where available.
  Details and confidence levels are in `docs/research/demo-data-calibration.md`.
- **Upload-ready sets:** `python scripts/build_account_datasets.py` builds `Accounts-Datasets/{America,Germany,UAE}/` (untracked): six CSVs each, in the platform's exact field names,
  metric and currency-free, plus a `README.txt` with the account settings and steps. Every file is checked with the platform's own mapping and transform, and all columns must map "exact".
- **Boundary files** for the map: `scripts/build_region_maps.py`.
- **Real reference data:** `data/public/` (source list in its README).

---

## 18. Conventions, gotchas and known limitations

### 18.1 Conventions

- **Layering:** respect the layer table. New backend package: classify it in `test_architecture.py`.
- **Tenant safety:** never bypass the tenant scope. Any cache must use `tenant_cache`; any file path must include the tenant id; use `tenant_context` in workers and scripts.
- **Services return plain data.** No ORM objects, sessions or framework types across the service boundary.
- **Errors:** raise `AppError` subclasses for anything the user can act on (the message must be safe to show); let everything else propagate to be logged with a reference.
- **Comments:** write none by default; add one only for a non-obvious *why*.
- **Web:** only `lib/api.ts` calls the backend; chart types stay unless a change adds value; use theme tokens (CSS variables), not hard-coded colours.
- **Commits:** commit under your own identity; do not push without being asked; never commit `.env`.

### 18.2 Gotchas learned the hard way

- Postgres RLS needs `NULLIF(...)` in the policy expression because a pooled connection that once served a tenant reverts the setting to `''`, and `''::uuid` would raise.
- Missing foreign-key child indexes make parent deletes quadratic.
- Do not run DDL tests while other database work runs (deadlocks). Do not run two test processes at once.
- `d3-geo` needs clockwise exterior rings; GeoJSON's standard is the opposite.
- Next.js drops proxied bodies over 10 MB unless configured (both for uploads).
- Models live in the container volume; train inside the stack.
- FastAPI file parameters should be `Annotated[UploadFile, File()]`, not a default `File(...)` (ruff `B008`).
- Windows: a leftover local dev server can silently hold a Docker-published port.

### 18.3 Known limitations and open work

- **Forecast accuracy** is unproven on real dealer data; see section 9.6 for measured findings and the proposed per-account method selection, honest intervals and on-screen accuracy.
  This is the most valuable next engineering step.
- **Operator MFA** is not built (the auth server supports TOTP; the enrolment and recovery flow needs design).
- **Infrastructure decisions pending:** hosting, TLS termination, SMTP provider for password-reset emails, backups. Rotate the API keys that were once committed.
- **Per-tenant duplication of news rows** for tenants sharing an edition (a shared table outside RLS would fix it; low priority while scoring is offline).
- **No schema migration tool** yet (`init-db` is idempotent but not a versioned migration).
- **Large uploads** are read fully into memory (capped at 500 MB).
- **Action Layer** (decision inbox, owners, impact tracking): pitched, deliberately paused until customer conversations show which one decision matters most.
  See `docs/research/customer-discovery.md`.
- **Demo data:** the UAE 2023 onward volume path is low confidence; repository sample CSVs under `data/samples/` are older than the generators.

---

## 19. Glossary and file map

**Glossary**

- **Tenant / account / organisation:** one customer dealer group.
- **Operator:** PredictaX staff who run the admin console; belongs to no tenant.
- **RLS:** PostgreSQL Row-Level Security; the database enforces tenant isolation.
- **Capabilities:** which data an account has, which decides which tabs it sees.
- **Play:** a ranked recommended action from the decision engine.
- **Rooftop / store:** one dealership location (a `Dealer` row).
- **Extras:** per-row JSON for uploaded columns with no canonical field.
- **Artifact:** a saved, signed model file.
- **WAPE:** weighted absolute percentage error (total absolute error over total actual), used in the backtest.
- **AUC:** how well a score ranks positives above negatives (0.5 is a coin flip).

**Where to look**

| I want to change... | Look in |
|---|---|
| what customers can upload | `backend/ingestion/catalog.py`, `mapping.py`, `pipeline.py` |
| how imports run | `backend/ingestion/jobs.py`, `backend/services/imports.py`, `backend/api/routers/admin_imports.py` |
| tenant isolation | `backend/db/rls.py`, `backend/db/connection.py`, `backend/core/request_context.py` |
| login and sessions | `backend/auth/client.py`, `backend/services/identity.py`, `backend/api/deps.py`, `backend/api/cookies.py` |
| a dashboard's data | `backend/services/<tab>.py`, `backend/repositories/`, `backend/analytics/` |
| a dashboard's screen | `web/src/features/<tab>/` |
| operator screens | `web-admin/src/features/` |
| models | `backend/ml/` |
| news | `backend/sentiment/` |
| config and secrets | `backend/core/config.py`, `.env.example`, `docker-compose.yml` |
| security rules | `docs/security.md`, this guide section 12 |
| the layer rules | `tests/unit/test_architecture.py` |
