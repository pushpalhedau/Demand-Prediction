import pytest

from backend.core import config
from backend.core.config import get_settings

STRONG = {
    "ENVIRONMENT": "production",
    "DATABASE_URL": "postgresql+psycopg2://predictax_app:Zq81vXkP2mNw@db.internal:5432/predictax",
    "ADMIN_DATABASE_URL": "postgresql+psycopg2://predictax_owner:Tt5rYh90LcVb@db.internal:5432/predictax",
    "SUPABASE_JWT_SECRET": "k9V2mX7qLr4TzB8wNc1YfH6sJd3PaGu5Ee0RoQxKiUlM",
    "AUTH_BASE_URL": "https://auth.example.com",
    "REDIS_URL": "redis://:S3cretRedisPw@redis.internal:6379/0",
}


@pytest.fixture
def env(monkeypatch):
    for key in ("ENVIRONMENT", "DATABASE_URL", "ADMIN_DATABASE_URL", "SUPABASE_JWT_SECRET", "AUTH_BASE_URL",
                "SUPABASE_URL", "REDIS_URL", "UPLOAD_DIR", "MODEL_DIR", "ALLOW_PAID_SENTIMENT", "XAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    def apply(values):
        for k, v in values.items():
            monkeypatch.setenv(k, v)
    return apply


def test_a_strong_production_configuration_passes(env):
    env(STRONG)
    settings = get_settings()
    assert settings.is_production and settings.problems() == []
    settings.assert_production_ready()


def test_development_defaults_are_accepted_in_development(env):
    settings = get_settings()
    assert not settings.is_production
    settings.assert_production_ready()          # only enforced in production


def test_production_refuses_development_defaults(env):
    env({"ENVIRONMENT": "production"})
    with pytest.raises(RuntimeError) as e:
        get_settings().assert_production_ready()
    text = str(e.value)
    assert "development password" in text and "SUPABASE_JWT_SECRET" in text and "AUTH_BASE_URL" in text


@pytest.mark.parametrize("override,expected", [
    ({"SUPABASE_JWT_SECRET": "short"}, "SUPABASE_JWT_SECRET"),
    ({"SUPABASE_JWT_SECRET": config.DEV_JWT_SECRET}, "SUPABASE_JWT_SECRET"),
    ({"DATABASE_URL": "postgresql+psycopg2://predictax_app:predictax_app_dev@db.internal/predictax"}, "development password"),
    ({"ADMIN_DATABASE_URL": STRONG["DATABASE_URL"]}, "must be different roles"),
    ({"AUTH_BASE_URL": "http://auth.example.com"}, "must use https"),
    ({"REDIS_URL": "redis://redis.internal:6379/0"}, "REDIS_URL has no password"),
])
def test_each_insecure_setting_is_reported(env, override, expected):
    env({**STRONG, **override})
    assert any(expected in p for p in get_settings().problems())


def test_plain_http_is_fine_inside_a_private_network_name_or_localhost(env):
    env({**STRONG, "AUTH_BASE_URL": "http://auth:9999"})
    assert get_settings().problems() == []


def test_paid_scoring_is_off_unless_switched_on(env):
    assert get_settings().allow_paid_sentiment is False
    env({"ALLOW_PAID_SENTIMENT": "yes"})
    assert get_settings().allow_paid_sentiment is True


def test_settings_are_read_fresh_so_changes_take_effect(env):
    env({"UPLOAD_DIR": "/tmp/a"})
    first = get_settings().upload_dir
    env({"UPLOAD_DIR": "/tmp/b"})
    assert get_settings().upload_dir != first


def test_the_model_signing_key_depends_on_the_auth_secret(env):
    env({"SUPABASE_JWT_SECRET": "a" * 40})
    a = get_settings().model_signing_key
    env({"SUPABASE_JWT_SECRET": "b" * 40})
    assert get_settings().model_signing_key != a
