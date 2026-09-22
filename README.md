# PredictaX

Multi-tenant demand intelligence for automobile dealer groups. Each customer account has its own login and sees only
its own data: forecasting, store performance, customer intelligence, inventory and market-sentiment dashboards, built
from CSV exports the operator uploads.

Two web apps:

| App | Who | What | Default URL |
|---|---|---|---|
| **Web app** (`web/`, Next.js + FastAPI) | everyone, one login page | customers land on their dashboard (light and dark themes, all seven tabs); PredictaX operators land on the admin console at `/admin` (accounts, settings, logins, access, import, retrain, audit log). The account decides, not the form. | http://localhost:3000 |
| Standalone admin console (`web-admin/`) | operators only | the previous, separate copy of the console. It still builds and works on its own port, but the same console is now part of `web/`. | http://localhost:3002 |

## Repository layout

```
backend/                 all logic; knows nothing about any web framework except the thin `api/` shell
  core/                  config, request scope, formatting, cache, errors, logging, security primitives
  db/                    engines, sessions, row-level security, ORM models
  repositories/          SQL access by domain (sales, dealers, customers, inventory, catalog)
  auth/                  client for the auth server (open-source Supabase Auth / GoTrue)
  analytics/             decision engine, year-over-year attribution, what-if model, benchmarks
  sentiment/             free news intake (Google News RSS), offline scoring, briefing
  ml/                    forecasting, segmentation, lead scoring, signed model artifacts
  ingestion/             field catalog, column mapping, transform + load pipeline, background jobs
  tenancy/               provisioning, capabilities, settings validation, audit trail
  services/              the only surface the API may call
  api/                   FastAPI shell for both Next.js apps (cookie sessions, JSON)
  cli.py                 operator command line (python -m backend.cli)
web/                     Next.js dashboard: src/app (routes), features/, components/, lib/ (api, i18n, format)
web-admin/               Next.js admin console: accounts, settings, logins, access, import, audit log
data/samples/            demo datasets (Germany)
docs/                    architecture, security, operations (archive/ = pre-multi-tenant material)
requirements/            base.txt (ranges), lock.txt (pinned, audited), dev.txt
scripts/                 one-off data generators
tests/                   unit/, integration/, e2e/
```

The boundary that matters: **the HTTP API reaches the backend only through `backend.services`**, and the Next.js apps
only ever talk to the API. `tests/unit/test_architecture.py` enforces the first, plus one-directional layering inside the
backend.

## Quick start (local development)

No Docker, no local database or auth server: every environment (local dev included) talks to a hosted Supabase
project (Postgres + Auth). Requires Python 3.11+ and Node 22.

```bash
python -m venv venv && venv/Scripts/activate            # Windows; use `source venv/bin/activate` elsewhere
pip install -r requirements/dev.txt && pip install -e . --no-deps
cp .env.example .env                                    # fill in your Supabase project's URL, keys and DB passwords

python -m backend.cli init-db                           # tables, row-level security, grants (idempotent)

# an operator login for the admin console, then start the API and the web app
python -m backend.cli create-operator --email you@example.com
python -m uvicorn backend.api.app:app --port 8000
(cd web && npm install && npm run dev)                                   # http://localhost:3000 (sign in as the operator: you land on /admin)
```

Onboarding a customer: sign in as the operator (the console is at `/admin`), **Accounts → Create a new account**, open it, **Import data**,
upload their CSVs, confirm the column matching, **Import and train**. See `docs/operations.md`.

**If your local `.env` points at the same Supabase project other people or a live deployment use**, treat it as a real
production database, not a sandbox: it holds whatever accounts and data are on it, and there is no separate copy to
reset. In particular, be careful with `reset-db` (drops every table) and the integration/e2e test suites below, which
create and delete tenants against whatever `DATABASE_URL`/`ADMIN_DATABASE_URL` your `.env` has configured.

## Tests

```bash
pytest -m unit                    # no database needed
pytest -m "unit or integration"   # integration tests need a real Postgres -- see the warning above before running
pytest                            # everything; tests skip themselves when a service they need is down
ruff check backend tests
bandit -r backend -ll
pip-audit -r requirements/lock.txt
```

## Documentation

- [`docs/developer-guide.md`](docs/developer-guide.md) — **start here**: the whole system in order (stack and why, data flow, security, running, recipes)
- [`docs/architecture.md`](docs/architecture.md) — layers, request flow, tenancy model, data flow
- [`docs/security.md`](docs/security.md) — threat model, controls, production checklist, known limits
- [`docs/operations.md`](docs/operations.md) — runbook: onboarding, retraining, secrets, backups, troubleshooting
