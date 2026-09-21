"""
Phase 1 smoke test for a hosted Supabase project (step 3.5 of DEPLOYMENT-EC2-MICRO.md).

Reads four values from the environment (never from this file), creates a throwaway user, and checks:
  1. the service_role key can create a confirmed user
  2. the anon key can sign that user in
  3. the access token uses an algorithm this app can verify (HS256 shared secret, or ES256/RS256 via the project's public keys)
  4. the APP'S OWN verifier (backend.auth.client.verify_access_token) accepts the real token, and rejects a tampered copy
  5. public sign-up is closed
Everything it creates is deleted at the end.

Run from the repo root in Git Bash:
  export SUPABASE_URL='https://<ref>.supabase.co' SUPABASE_ANON_KEY='...' SUPABASE_SERVICE_ROLE_KEY='...' SUPABASE_JWT_SECRET='...'
  venv/Scripts/python.exe scripts/supabase_smoke_test.py
"""
import os
import sys
import uuid

import jwt
import requests

# Use the app's own verifier. Blank AUTH_BASE_URL so the repo's local-development .env cannot redirect it to localhost.
os.environ["AUTH_BASE_URL"] = ""
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

TIMEOUT = 15


def need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Set {name} first (see the docstring).")
    return value


url = need("SUPABASE_URL").rstrip("/")
anon = need("SUPABASE_ANON_KEY")
service = need("SUPABASE_SERVICE_ROLE_KEY")
secret = need("SUPABASE_JWT_SECRET")
auth = f"{url}/auth/v1"

results: list[tuple[str, bool, str]] = []
created: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
    return ok


def admin_headers() -> dict:
    return {"apikey": service, "Authorization": f"Bearer {service}", "Content-Type": "application/json"}


# Keys must be the legacy JWT-style ones: the app sends the service key as a Bearer token.
for label, key in (("anon key", anon), ("service_role key", service)):
    if key.startswith("sb_"):
        check(f"{label} is a legacy JWT key", False,
              "it starts with 'sb_' (new-style key). Use the *Legacy* tab under Project Settings -> API Keys.")

email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
password = f"Smoke-{uuid.uuid4().hex[:12]}-Aa1"

try:
    r = requests.post(f"{auth}/admin/users", headers=admin_headers(), timeout=TIMEOUT,
                      json={"email": email, "password": password, "email_confirm": True,
                            "app_metadata": {"role": "smoke_test"}})
    ok = r.status_code in (200, 201)
    check("service_role key can create a confirmed user", ok, "" if ok else f"HTTP {r.status_code}: {r.text[:200]}")
    if ok:
        created.append(r.json()["id"])

    token = ""
    if created:
        r = requests.post(f"{auth}/token", params={"grant_type": "password"}, timeout=TIMEOUT,
                          headers={"apikey": anon, "Content-Type": "application/json"},
                          json={"email": email, "password": password})
        ok = r.status_code == 200
        check("anon key can sign the user in", ok, "" if ok else f"HTTP {r.status_code}: {r.text[:200]}")
        if ok:
            token = r.json()["access_token"]

    if token:
        alg = jwt.get_unverified_header(token).get("alg", "?")
        check("access token algorithm is one the app verifies", alg in ("HS256", "ES256", "RS256"), alg)
        from backend.auth.client import AuthError, identity_from_claims, verify_access_token
        try:
            claims = verify_access_token(token)
            meta = claims.get("app_metadata") or {}
            check("the app's verifier accepts the real token", True,
                  f"alg={alg}, sub={claims['sub'][:8]}..., app_metadata.role={meta.get('role')}")
            try:
                identity_from_claims(claims)
                check("a user with no tenant is refused", False, "identity_from_claims accepted a user without tenant_id")
            except AuthError:
                check("a user with no tenant is refused", True)
        except AuthError as e:
            check("the app's verifier accepts the real token", False, f"{e} (alg={alg}; check SUPABASE_URL / SUPABASE_JWT_SECRET)")
        head, payload, sig = token.split(".")
        tampered = f"{head}.{payload}.{'A' if sig[0] != 'A' else 'B'}{sig[1:]}"
        try:
            verify_access_token(tampered)
            check("a tampered token is rejected", False, "the verifier accepted a token with an altered signature")
        except AuthError:
            check("a tampered token is rejected", True)

    r = requests.post(f"{auth}/signup", headers={"apikey": anon, "Content-Type": "application/json"}, timeout=TIMEOUT,
                      json={"email": f"nosignup-{uuid.uuid4().hex[:8]}@example.com", "password": f"Nope-{uuid.uuid4().hex[:12]}-Aa1"})
    if r.status_code == 200:
        try:
            created.append(r.json().get("id") or r.json()["user"]["id"])
        except (KeyError, ValueError, TypeError):
            pass
    check("public sign-up is closed", r.status_code != 200,
          f"HTTP {r.status_code}" if r.status_code != 200 else "sign-up WORKED: switch off 'Allow new users to sign up' in the dashboard")
finally:
    for user_id in created:
        d = requests.delete(f"{auth}/admin/users/{user_id}", headers=admin_headers(), timeout=TIMEOUT)
        print(f"cleanup: deleted {user_id[:8]}... (HTTP {d.status_code})")

failed = [name for name, ok, _ in results if not ok]
print("\nRESULT:", "ALL PASSED. Continue to section 4." if not failed else f"{len(failed)} FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)
