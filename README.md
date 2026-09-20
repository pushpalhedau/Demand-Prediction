# PredictaX

Multi-tenant demand intelligence for automobile dealer groups. Each customer account has its own login and sees only
its own data: forecasting, store performance, customer intelligence, inventory and market-sentiment dashboards, built
from CSV exports the operator uploads.

Four web apps:

| App | Who | What | Default URL |
|---|---|---|---|
| **Dashboard** (`web/`, Next.js + FastAPI) | dealer-group staff | the new customer dashboard, light and dark themes, all seven tabs | http://localhost:3000 |
| **Admin console** (`web-admin/`, Next.js + FastAPI) | PredictaX operators only | accounts, settings, logins, access, retrain, audit log | http://localhost:3002 |
| **Classic dashboard** (`frontend/customer_app`, Streamlit) | dealer-group staff | the previous dashboard, kept until the new one is signed off | http://localhost:8501 |
| **Classic admin console** (`frontend/admin_console`, Streamlit) | PredictaX operators only | still the only place to **import data**; everything else has moved to the new console above | http://localhost:8502 |

## Repository layout

```
backend/                 all logic; knows nothing about Streamlit or any web framework
  core/                  config, request scope, formatting, cache, errors, logging, security primitives
  db/                    engines, sessions, row-level security, ORM models
  repositories/          SQL access by domain (sales, dealers, customers, inventory, catalog)
  auth/                  client for the auth server (open-source Supabase Auth / GoTrue)
  analytics/             decision engine, year-over-year attribution, what-if model, benchmarks
  sentiment/             free news intake (Google News RSS), offline scoring, briefing
  ml/                    forecasting, segmentation, lead scoring, signed model artifacts
  ingestion/             field catalog, column mapping, transform + load pipeline, background jobs
  tenancy/               provisioning, capabilities, settings validation, audit trail
  services/              the only surface the frontends may call
  api/                   FastAPI shell for the Next.js dashboard (cookie sessions, JSON)
  cli.py                 operator command line (python -m backend.cli)
frontend/                Streamlit apps (classic dashboard, admin console)
  customer_app/          main.py, auth.py, views/
  admin_console/         main.py, auth.py, views/
  shared/                ui helpers, i18n, HTML-safety, error display, session bridge
  assets/                stylesheet, images
web/                     Next.js dashboard: src/app (routes), features/, components/, lib/ (api, i18n, format)
web-admin/               Next.js admin console: accounts, settings, logins, access, audit log (no import yet)
deploy/postgres/         database bootstrap (roles, default-deny)
data/samples/            demo datasets (Germany)
docs/                    architecture, security, operations (archive/ = pre-multi-tenant material)
requirements/            base.txt (ranges), lock.txt (pinned, audited), dev.txt
scripts/                 one-off data generators
tests/                   unit/, integration/, e2e/
```

The boundary that matters: **the frontend reaches the backend only through `backend.services`**, and the backend never
imports Streamlit. `tests/unit/test_architecture.py` enforces both, plus one-directional layering inside the backend.

## Quick start (local development)

Requires Python 3.11+ and Docker.

```bash
python -m venv venv && venv/Scripts/activate            # Windows; use `source venv/bin/activate` elsewhere
pip install -r requirements/dev.txt && pip install -e . --no-deps
cp .env.example .env

docker compose up -d db auth                            # Postgres + auth server
python -m backend.cli init-db                           # tables, row-level security, grants

# an operator login for the admin console, then start the apps
python -m backend.cli create-operator --email you@example.com
streamlit run frontend/admin_console/main.py --server.port 8502 --server.maxUploadSize 500
streamlit run frontend/customer_app/main.py  --server.port 8501          # classic dashboard

# the new dashboard and admin console: API + two Next.js apps
python -m uvicorn backend.api.app:app --port 8000
(cd web && npm install && npm run dev)                                   # http://localhost:3000
(cd web-admin && npm install && npm run dev)                             # http://localhost:3002
```

Full stack in containers (adds Redis, a background worker, and all four web apps):

```bash
docker compose up -d --build
```

Onboarding a customer: on the new admin console (3002), **Accounts → Create a new account**; on the classic console
(8502), open it and **Import data**, upload their CSVs, confirm the column matching, **Import and train**. See
`docs/operations.md`.

## Tests

```bash
pytest -m unit                    # no services needed
pytest -m "unit or integration"   # needs: docker compose up -d db
pytest                            # everything; tests skip themselves when a service they need is down
ruff check backend frontend tests
bandit -r backend frontend -ll
pip-audit -r requirements/lock.txt
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — layers, request flow, tenancy model, data flow
- [`docs/security.md`](docs/security.md) — threat model, controls, production checklist, known limits
- [`docs/operations.md`](docs/operations.md) — runbook: onboarding, retraining, secrets, backups, troubleshooting
