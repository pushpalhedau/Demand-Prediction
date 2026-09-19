"""
Operator-facing account management: create and configure customer accounts, their logins and status.

Every function here acts across tenants on purpose (it is what an operator is for), so it is reachable
only from the admin console, whose users must hold the platform_admin role.
"""
from __future__ import annotations

import re
import secrets
from typing import Any

from backend.auth import client as auth_client
from backend.core.errors import AuthError, InvalidSetting
from backend.tenancy import provision
from backend.tenancy.settings import validate_config
from backend.tenancy.summary import account_summary

__all__ = ["AuthError", "InvalidSetting", "account_summary", "add_login", "create_account", "get_account",
           "list_accounts", "list_logins", "reset_login_password", "set_account_status", "slugify",
           "update_account_settings"]

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "AED": "AED", "SAR": "SAR", "CHF": "CHF",
                    "CAD": "$", "AUD": "$", "JPY": "¥", "CNY": "¥"}
REGION_LABELS = ["Region", "State", "Province", "Emirate", "Bundesland", "County"]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def list_accounts() -> list[dict[str, Any]]:
    return provision.all_tenants()


def get_account(slug: str) -> dict[str, Any]:
    return provision.get_tenant(slug)


def create_account(name: str, slug: str, admin_email: str, admin_password: str | None, config: dict) -> dict:
    """Create an account and its first admin login. Returns the credentials (shown once by the caller)."""
    clean = validate_config(config)
    password = admin_password or secrets.token_urlsafe(12)
    return provision.create_tenant(slug or slugify(name), name.strip(), admin_email.strip(), password, config=clean)


def update_account_settings(slug: str, config: dict) -> dict:
    return provision.set_config(slug, validate_config(config))


def set_account_status(slug: str, status: str) -> None:
    provision.set_status(slug, status)


def list_logins(tenant_id) -> list[dict[str, Any]]:
    """The account's users (email, role, last sign-in, created)."""
    return [
        {"id": u["id"], "email": u["email"], "role": (u.get("app_metadata") or {}).get("role", ""),
         "last_sign_in": (u.get("last_sign_in_at") or "never")[:16], "created": (u.get("created_at") or "")[:10]}
        for u in auth_client.users_of_tenant(tenant_id)
    ]


def add_login(slug: str, email: str, password: str | None, role: str) -> dict:
    return provision.add_user(slug, email.strip(), password or None, role)


def reset_login_password(user_id: str) -> str:
    """Set a new random password and return it (shown once by the caller)."""
    new_password = secrets.token_urlsafe(12)
    auth_client.admin_set_password(user_id, new_password)
    return new_password

