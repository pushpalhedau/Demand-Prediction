# Security

## What we protect, and from whom

| Asset | Threat | Main controls |
|---|---|---|
| One customer's data | another customer, or a bug in our code, reading it | Postgres row-level security; restricted DB role; tenant-keyed caches, models, uploads |
| Operator powers (create accounts, read all data) | a customer or outsider using them | separate operator identity; console bound to localhost; audit log; idle timeout; login throttling |
| Credentials and tokens | theft, guessing, forgery | throttled sign-in; JWT `exp/sub/aud` required; tokens only in httpOnly cookies; no secrets in git or images |
| The web tier | XSS, injection, tampering | escaped HTML, validated settings, parameterised SQL, signed model files, hardened XML, upload limits |
| The deployment | insecure defaults | production config refuses development secrets; non-root read-only containers; localhost-only ports |

## Controls

**Isolation (defence in depth)**
* RLS `USING` + `WITH CHECK` on every tenant table, `FORCE`d so even the table owner is subject to it.
* The app role is not a superuser, has no `BYPASSRLS`, cannot `CREATE`, and holds explicit grants only; the database
  bootstrap grants nothing by default and `init-db` revokes every non-tenant table from it.
* The HTTP API cannot import the database, ORM or SQLAlchemy, only `backend.services`: `tests/unit/test_architecture.py` fails the build.
* Verified by tests: same IDs in two tenants, no-tenant reads return nothing, cross-tenant writes are rejected,
  pooled connections do not carry a tenant to the next borrower, caches never cross tenants.

**Identity**
* Customer and operator logins are different kinds; each app rejects the other's tokens.
* Tenant and role come from `app_metadata`, which users cannot edit (tested: editing `user_metadata` changes nothing).
* Sign-in is throttled per account on the server (5 failures → 15-minute lockout, shared across instances via Redis); the auth server rate-limits too.
* Tokens are verified on every refresh; a suspended account is signed out within 5 minutes.
* Operators are signed out after 30 minutes idle; passwords chosen by a person must be ≥ 10 characters.
* Deleting an account is irreversible and needs the account's short id typed twice (UI and API); it removes the
  logins, every row, uploads and models, and the audit trail keeps a record.
* The customer app and the admin console use different session-cookie names and different FastAPI dependencies
  (`backend/api/deps.py`), so a browser with both open at once can never mix the two up.

**Application**
* React escapes everything it renders and no page injects raw HTML; news links must be plain http(s) (`web/src/lib/safe.ts`).
* Tenant settings that can reach markup (currency symbol, labels) are validated against strict patterns, not escaped.
* Exception text and stack traces never reach the browser; unexpected errors are logged with a reference id.
* Trained model files are HMAC-signed and verified before unpickling; a tampered file is refused, never executed.
* Untrusted feed XML is parsed with `defusedxml`. CSV uploads have size, row and column limits and are read as text.
* SQL is parameterised; the only interpolated identifiers come from our own model metadata.

**Operations**
* The audit trail (`audit_events`) records operator sign-ins, account changes, imports, retrains and resets. It is
  append-only (a trigger rejects update, delete and truncate) and unreadable by the app role. Secrets are never stored in it.
* Containers run as a non-root user, read-only, all capabilities dropped, `no-new-privileges`; every published port is
  bound to `127.0.0.1`; Redis requires a password; images are tag-pinned; Python dependencies are pinned in
  `requirements/lock.txt` and audited (`pip-audit`), code is scanned (`bandit`, `ruff`).

## Production checklist

1. Set `ENVIRONMENT=production`. Startup then fails unless: `SUPABASE_JWT_SECRET` is ≥ 32 random characters, the
   database passwords are not the development ones, the app and owner roles differ, auth/Supabase URLs are `https`
   (or a private hostname), and Redis has a password.
2. Provide secrets through your platform's secret store. Generate: `APP_DB_PASSWORD`, `OWNER_DB_PASSWORD`,
   `AUTH_DB_PASSWORD`, `REDIS_PASSWORD`, `SUPABASE_JWT_SECRET`.
3. Put a TLS-terminating reverse proxy in front of the customer dashboard. Add: HSTS, `X-Content-Type-Options: nosniff`,
   `Referrer-Policy: same-origin`, `Content-Security-Policy: frame-ancestors 'none'` (the API already sends nosniff,
   no-referrer-style and frame-deny headers on its own responses).
4. Do **not** publish the admin console. Reach it over a VPN or SSH tunnel.
5. Configure SMTP on the auth server and set `GOTRUE_MAILER_AUTOCONFIRM` to `false` so password reset and
   invitation emails work.
6. Back up Postgres (it holds data, users and the audit trail) and the `models`/`uploads` volumes; test a restore.
7. Rotate any key that was ever committed. `.env` was tracked in this repository's earlier history, including
   `XAI_API_KEY` and `SERPER_API_KEY`: treat them as exposed and replace them.

## Known limitations

* The tenant cache is per process. Login throttling is shared across instances through Redis when `REDIS_URL` is
  set (fixed 15-minute window); if Redis is unreachable it falls back to a per-process limit rather than blocking
  sign-in, and the auth server's own rate limits remain the backstop.
* Operators have a single role and no second factor yet; audit records can be removed only by someone who can drop the
  trigger as the database owner, so restrict that role.
* News is public but attacker-influenceable text; it is escaped everywhere, and scoring is offline by default.
