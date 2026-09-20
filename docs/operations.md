# Operations runbook

## Start and stop

```bash
docker compose up -d db auth              # minimum for local development
docker compose up -d --build              # full stack: + redis, worker, api, frontend (3000), admin-frontend (3002), classic web (8501), admin (8502)
docker compose stop                       # stop, keep data
docker compose down -v                    # DANGER: also deletes the database, uploads and models
```

First run on an empty database, and after every schema or model change:

```bash
python -m backend.cli init-db             # creates tables, applies row-level security and grants (idempotent)
```

`reset-db --yes` drops every table (development only).

## Run the new dashboard from source (development)

```bash
docker compose up -d db auth
python -m uvicorn backend.api.app:app --reload --port 8000     # API (docs at /api/docs in development)
cd web && npm install && npm run dev                            # dashboard on http://localhost:3000
cd web-admin && npm install && npm run dev                      # admin console on http://localhost:3002
```

`API_URL` (default `http://localhost:8000`) tells each app where to proxy `/api`. Quality gates for both web apps:
`npm run lint`, `npm run typecheck`, `npm test`, `npm run build` (run from `web/` or `web-admin/` respectively).

## Operators

```bash
python -m backend.cli create-operator --email you@example.com     # prints a generated password once
```

Sign in at the admin console (port 3002) for accounts, settings, logins, access, import and the audit log. The
classic console (port 8502) still works and shares the same accounts, but is kept only until the new one has run
in production for a while. To change an operator's password, use the auth server admin API or delete and recreate
the login. Every sign-in and action is in **Audit log**.

## Onboard a customer

1. **Accounts → Create a new account** (port 3002). Name, currency, language, what they call regions ("State",
   "Emirate"…), country for local news, and their first admin's email. The password is shown once: send it over a
   secure channel.
2. Open the account → **Import data**. Upload their CSVs (only the sales file is required; the templates list the
   standard columns, but their own names are matched automatically).
3. Check the column matching, especially anything marked as a guess, the distance unit (km/miles), date order and
   decimal separator. **Check the data** dry-runs a sample.
4. **Import and train.** Watch progress; the account's dashboards go live when it finishes. A failed import changes
   nothing and says why.

**Monthly refresh:** import again with *Add to their existing data* (skips rows already loaded) or *Replace all their
data*. The confirmed mapping is remembered.

## Retrain, users, suspension

All on the new admin console (port 3002):

* **History → Retrain models now** rebuilds the ML models from the data already loaded.
* **Logins**: add users (Manage = can see everything; View only = dashboards), reset a password.
* **Access → Suspend** blocks every login for the account; data is kept. Users are signed out within 5 minutes.

## Secrets and configuration

All configuration is environment variables (see `.env.example`); nothing else reads the environment.
Rotate `SUPABASE_JWT_SECRET`: existing logins stop working and **all saved model files become unverifiable**
(they are signed with a key derived from it), so retrain every account afterwards.

## Backups and restore

Back up Postgres (`pg_dump -Fc`), and the `uploads` and `models` volumes. Restore into an empty database, run
`init-db`, then restore the volumes. Models can always be rebuilt with **Retrain**.

## Scaling notes

* Add capacity for imports by scaling workers: `docker compose up -d --scale worker=3`.
* The customer app scales horizontally behind a load balancer with sticky sessions (sessions live in server memory).
* Put PgBouncer in front of Postgres in transaction-pooling mode if connections become the limit; tenant scoping is
  transaction-local, so it is compatible.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "Your account is being set up" | the account has no sales yet: import data |
| Customer tab says the lead model is not trained | run **Retrain models** (also required after a secret rotation) |
| Import "failed", nothing changed | read the message; usually a required column is missing or every date is unreadable |
| `Refusing to start with an insecure production configuration` | `ENVIRONMENT=production` with a development default; fix what it lists |
| Operator login says invalid credentials | wrong password, or a customer account (customer logins cannot use the console) |
| "Too many failed attempts" | throttle: wait 15 minutes, or restart the app to clear it |
| Console cannot reach the auth server | `docker compose up -d auth`; check `AUTH_BASE_URL` |
| Something failed with a reference id | search the server logs for `[ref=<id>]` |

## Upgrading from a root-owned volume

Containers now run as uid 10001. A `uploads` or `models` volume created by an older, root-run image is not writable
by it (imports fail with "Read-only file system" or "Permission denied"). Fix once:

```bash
docker compose run --rm --no-deps -u root --cap-add CHOWN --cap-add DAC_OVERRIDE --entrypoint sh worker \
  -c "chown -R 10001:10001 /data/uploads"
```

New volumes need nothing: they inherit ownership from the image.
