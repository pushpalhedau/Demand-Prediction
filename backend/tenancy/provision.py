import re
import secrets
import shutil

from backend.auth import client as auth_client
from backend.core.config import get_settings
from backend.db.connection import get_admin_session
from backend.db.models import Tenant

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}$")


def create_tenant(slug: str, name: str, admin_email: str, admin_password: str = None,
                  config: dict = None, plan: str = None, create_login: bool = True) -> dict:
    """Create a tenant and (unless create_login is False) its first admin login."""
    if not _SLUG_RE.match(slug):
        raise ValueError("slug must be 2-62 chars of lowercase letters, digits and hyphens")

    db = get_admin_session()
    try:
        if db.query(Tenant).filter(Tenant.slug == slug).first():
            raise ValueError(f"tenant slug {slug!r} already exists")
        tenant = Tenant(slug=slug, name=name, plan=plan, config=config or {})
        db.add(tenant)
        db.commit()
        tenant_id = tenant.id

        result = {"tenant_id": str(tenant_id), "slug": slug, "email": admin_email, "password": None}
        if create_login:
            password = admin_password or secrets.token_urlsafe(12)
            try:
                auth_client.admin_create_user(admin_email, password, tenant_id, role="tenant_admin")
            except Exception:
                db.query(Tenant).filter(Tenant.id == tenant_id).delete()   # don't leave a login-less orphan
                db.commit()
                raise
            result["password"] = password
        return result
    finally:
        db.close()


def get_tenant_id(slug: str):
    db = get_admin_session()
    try:
        t = db.query(Tenant).filter(Tenant.slug == slug).first()
        if t is None:
            raise ValueError(f"no tenant with slug {slug!r}")
        return t.id
    finally:
        db.close()


def list_tenants() -> list:
    db = get_admin_session()
    try:
        return [(str(t.id), t.slug, t.name, t.status) for t in db.query(Tenant).order_by(Tenant.created_at)]
    finally:
        db.close()


def add_user(slug: str, email: str, password: str = None, role: str = "tenant_user") -> dict:
    """Give an existing tenant another login (tenant_admin can upload data; tenant_user can only view)."""
    if role not in ("tenant_admin", "tenant_user"):
        raise ValueError("role must be tenant_admin or tenant_user")
    tenant_id = get_tenant_id(slug)
    password = password or secrets.token_urlsafe(12)
    auth_client.admin_create_user(email, password, tenant_id, role=role)
    return {"tenant_id": str(tenant_id), "email": email, "password": password, "role": role}


def set_config(slug: str, cfg: dict) -> dict:
    """Merge display settings into a tenant's config (operator action, owner credentials)."""
    db = get_admin_session()
    try:
        t = db.query(Tenant).filter(Tenant.slug == slug).one()
        t.config = {**(t.config or {}), **cfg}
        db.commit()
        return dict(t.config)
    finally:
        db.close()


def create_operator(email: str, password: str = None) -> dict:
    """Create a platform operator login (stored in the auth database like every other login)."""
    password = password or secrets.token_urlsafe(14)
    auth_client.admin_create_user(email, password, tenant_id=None, role="platform_admin")
    return {"email": email, "password": password}


def set_status(slug: str, status: str) -> None:
    if status not in ("active", "suspended"):
        raise ValueError("status must be active or suspended")
    db = get_admin_session()
    try:
        db.query(Tenant).filter(Tenant.slug == slug).update({"status": status})
        db.commit()
    finally:
        db.close()


def delete_tenant(slug: str) -> dict:
    """
    Permanently remove a tenant: its logins, every data row (cascade), uploaded files and trained models.
    Irreversible. Returns counts so the caller can tell the operator what went.
    """
    tenant_id = get_tenant_id(slug)
    logins = auth_client.users_of_tenant(tenant_id)
    for user in logins:
        auth_client.admin_delete_user(user["id"])

    db = get_admin_session()
    try:
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()
        db.commit()
    finally:
        db.close()

    settings = get_settings()
    folders = [settings.upload_dir / str(tenant_id)]
    if settings.model_dir.exists():
        folders += [kind / str(tenant_id) for kind in settings.model_dir.iterdir() if kind.is_dir()]
    for folder in folders:
        shutil.rmtree(folder, ignore_errors=True)
    return {"logins": len(logins)}


def get_tenant(slug: str) -> dict:
    db = get_admin_session()
    try:
        t = db.query(Tenant).filter(Tenant.slug == slug).one()
        return {"id": t.id, "slug": t.slug, "name": t.name, "status": t.status, "config": dict(t.config or {}),
                "created_at": t.created_at}
    finally:
        db.close()


def all_tenants() -> list:
    db = get_admin_session()
    try:
        return [{"id": t.id, "slug": t.slug, "name": t.name, "status": t.status,
                 "config": dict(t.config or {}), "created_at": t.created_at}
                for t in db.query(Tenant).order_by(Tenant.created_at.desc())]
    finally:
        db.close()
