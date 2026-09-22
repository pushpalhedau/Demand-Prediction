# Operations runbook

No Docker: there is no local database, auth server, queue or worker container. Every environment -- local
development included -- talks to a hosted Supabase project (Postgres + Auth) over the network, configured entirely
through `.env` (see `.env.example`). The API and each Next.js app are plain processes (`uvicorn`, `next dev`/`next
start`, or a systemd unit in production); there is nothing to "start the stack".

## Start and stop

First run on an empty database, and after every schema change:

```bash
python -m backend.cli init-db             # creates tables, applies row-level security and grants (idempotent)
```

`reset-db --yes` drops every table. **This is irreversible and, if your `.env` points at a shared or production
project, destroys everyone's data** -- there is no separate "the container's volume" to fall back on any more.

## Run the new dashboard from source (development)

```bash
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

Sign in on the normal login page (http://localhost:3000/login) with an operator account: you land on the admin console at `/admin` (the standalone `web-admin/` copy on port 3002 also still works) for accounts, settings, logins, access, import and the audit log. To change an operator's password, use the auth server admin API or delete and recreate
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
* Every import trains the account's models automatically. To retrain every account at once (for example after a
  release that changes the models), run `python -m backend.cli train --all` from a shell that has the same `.env`
  (same `MODEL_DIR`) as wherever the API reads model files from -- training on a machine that saves to a different
  `MODEL_DIR` than the API reads from will make training look like it worked while the API still sees the old models.
* **Logins**: add users (Manage = can see everything; View only = dashboards), reset a password.
* **Access → Suspend** blocks every login for the account; data is kept. Users are locked out within about a minute.
* **Access → Delete this account** removes the account, logins, data, uploads and models for good (type its short id
  to confirm). Take a backup first if there is any doubt.

## Secrets and configuration

All configuration is environment variables (see `.env.example`); nothing else reads the environment.
Rotate `SUPABASE_JWT_SECRET`: existing logins stop working and **all saved model files become unverifiable**
(they are signed with a key derived from it), so retrain every account afterwards.

## Backups and restore

The database is Supabase's to back up (check your plan's backup schedule and retention; the free tier has none).
Additionally back up the `UPLOAD_DIR` and `MODEL_DIR` directories on whatever disk the API runs from. Restore into
an empty database, run `init-db`, then restore those two directories. Models can always be rebuilt with **Retrain**
instead, as long as the imported data is still there.

## Scaling notes

* Imports run in a background thread inside the API process (no separate worker/queue); a very large import can
  compete with request handling on that same process. If import volume grows, the fix is to run more API instances
  behind a load balancer, or reintroduce a Redis-backed queue (`REDIS_URL`, already supported in `backend/ingestion/jobs.py`)
  and a separate worker process.
* The API and both web apps are stateless (sessions are cookies holding signed tokens), so they scale horizontally
  behind a load balancer with no sticky sessions.
* Use Supabase's session pooler (not a direct connection) if you run more than a handful of API instances against
  it, and keep each instance's `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` modest -- the pooler's own connection limit is shared
  across every instance and every other consumer of that project.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "Your account is being set up" | the account has no sales yet: import data |
| Lead Close Score says the model "has not been trained yet" | run **Retrain models** (also required after a secret rotation) |
| Lead Close Score says the model "could not be trained" | the message gives the reason (too few sales linked to customers, or no won/lost test drives in the sales file). Fix the data and re-import; a failed retrain removes the old model rather than leaving stale scores |
| Import "failed", nothing changed | read the message; usually a required column is missing or every date is unreadable |
| `Refusing to start with an insecure production configuration` | `ENVIRONMENT=production` with a development default; fix what it lists |
| Operator login says invalid credentials | wrong password, or a customer account (customer logins cannot use the console) |
| "Too many failed attempts" | throttle: wait 15 minutes. If `REDIS_URL` is set, clear it early by deleting the `throttle:*` keys in Redis (`redis-cli -a $REDIS_PASSWORD --scan --pattern "throttle:*"`); if `REDIS_URL` is unset (the default), the throttle is per-process, so restarting the API clears it |
| Console cannot reach the auth server | check `SUPABASE_URL`/`AUTH_BASE_URL` in `.env` and that the Supabase project is reachable (not paused) |
| Something failed with a reference id | search the server logs for `[ref=<id>]` |
