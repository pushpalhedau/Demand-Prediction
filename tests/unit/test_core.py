import uuid

import pandas as pd
import pytest

from backend.core import cache as cache_module
from backend.core.cache import tenant_cache
from backend.core.errors import AuthError, TenantNotSet
from backend.core.formatting import cur, cur_code, fmt_date, fmt_money, fmt_num, fmt_pct
from backend.core.request_context import (
    TenantProfile,
    bind_request,
    clear_request,
    current_language,
    current_profile,
    current_tenant_id,
    require_tenant_id,
    tenant_context,
)
from backend.core.security import LoginThrottle


@pytest.fixture(autouse=True)
def _clean_scope():
    clear_request()
    yield
    clear_request()


# ── request scope ───────────────────────────────────────────────────────────

def test_with_no_scope_there_is_no_tenant_and_requiring_one_fails_closed():
    assert current_tenant_id() is None
    with pytest.raises(TenantNotSet):
        require_tenant_id()


def test_bound_profile_sets_tenant_language_and_presentation():
    tid = uuid.uuid4()
    bind_request(TenantProfile.from_config(tid, "Acme", {"currency": "GBP", "currency_symbol": "£", "language": "de"}))
    assert current_tenant_id() == tid and current_profile().name == "Acme"
    assert current_language() == "de" and cur_code() == "GBP" and cur() == "£"


def test_clearing_the_request_forgets_the_tenant():
    bind_request(TenantProfile.from_config(uuid.uuid4(), "Acme", {}))
    clear_request()
    assert current_tenant_id() is None and current_profile() is None


def test_an_explicit_tenant_context_wins_and_never_mixes_with_another_tenants_profile():
    bound, other = uuid.uuid4(), uuid.uuid4()
    bind_request(TenantProfile.from_config(bound, "Bound", {"currency": "USD"}))
    with tenant_context(other):
        assert current_tenant_id() == other
        assert current_profile() is None          # the bound profile belongs to a different tenant
    assert current_tenant_id() == bound


def test_scopes_do_not_leak_between_threads():
    import threading
    bind_request(TenantProfile.from_config(uuid.uuid4(), "Main", {}))
    seen = []
    t = threading.Thread(target=lambda: seen.append(current_tenant_id()))
    t.start()
    t.join()
    assert seen == [None]


# ── tenant-keyed cache ──────────────────────────────────────────────────────

def _counting():
    calls = []

    @tenant_cache(ttl=60)
    def load(filters, _big=None):
        calls.append(filters)
        return pd.DataFrame({"n": [1, 2, 3]})

    return load, calls


def test_cache_never_serves_one_tenants_result_to_another():
    load, calls = _counting()
    a, b = uuid.uuid4(), uuid.uuid4()
    with tenant_context(a):
        load({"x": 1})
        load({"x": 1})
    with tenant_context(b):
        load({"x": 1})
    assert len(calls) == 2            # once per tenant, second call for `a` was a hit


def test_cache_requires_a_tenant():
    load, _ = _counting()
    with pytest.raises(TenantNotSet):
        load({"x": 1})


def test_callers_cannot_corrupt_the_cached_value():
    load, _ = _counting()
    with tenant_context(uuid.uuid4()):
        first = load({"x": 1})
        first.loc[0, "n"] = 999
        assert load({"x": 1}).loc[0, "n"] == 1


def test_underscore_arguments_are_left_out_of_the_key():
    load, calls = _counting()
    with tenant_context(uuid.uuid4()):
        load({"x": 1}, _big=pd.DataFrame({"a": [1]}))
        load({"x": 1}, _big=pd.DataFrame({"a": [2]}))
    assert len(calls) == 1


def test_entries_expire(monkeypatch):
    load, calls = _counting()
    clock = {"t": 1000.0}
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: clock["t"])
    with tenant_context(uuid.uuid4()):
        load({"x": 1})
        clock["t"] += 61
        load({"x": 1})
    assert len(calls) == 2


def test_cache_is_bounded():
    calls = []

    @tenant_cache(ttl=60, maxsize=3)
    def load(i):
        calls.append(i)
        return i

    with tenant_context(uuid.uuid4()):
        for i in range(10):
            load(i)
        load(0)                    # evicted long ago: recomputed
    assert calls.count(0) == 2


# ── formatting ──────────────────────────────────────────────────────────────

def _profile(**cfg):
    bind_request(TenantProfile.from_config(uuid.uuid4(), "T", cfg))


def test_english_money_uses_the_tenants_symbol_and_side():
    _profile(currency="USD", currency_symbol="$", language="en")
    assert fmt_money(1_234_567) == "$1.2M" and fmt_money(940_000) == "$940K"
    assert fmt_money(1234, compact=False) == "$1,234"


def test_alphabetic_symbols_get_a_space():
    _profile(currency="AED", currency_symbol="AED", language="en")
    assert fmt_money(3_040_000_000) == "AED 3.04B"


def test_german_uses_german_separators_and_a_trailing_symbol():
    _profile(currency="EUR", currency_symbol="€", language="de")
    assert fmt_money(1_234_567, compact=False) == "1.234.567 €"
    assert fmt_money(742_000_000) == "742,0 Mio. €"
    assert fmt_num(1234.5, 1) == "1.234,5" and fmt_pct(12.4) == "12,4 %"


def test_explicit_symbol_position_overrides_the_language_default():
    _profile(currency="EUR", currency_symbol="€", language="de", symbol_position="prefix")
    assert fmt_money(1000, compact=False) == "€1.000"


def test_missing_values_render_as_a_dash_or_na():
    _profile(language="en")
    assert fmt_num(None) == "n/a" and fmt_pct(None) == "n/a" and fmt_date(None) == "n/a"


# ── login throttle ──────────────────────────────────────────────────────────

def test_throttle_locks_an_account_after_repeated_failures_and_case_does_not_matter():
    t = LoginThrottle(max_failures=3, window_seconds=60, lockout_seconds=120)
    for _ in range(3):
        t.check("Person@Example.com")
        t.record_failure("person@example.com")
    with pytest.raises(AuthError, match="Too many failed attempts"):
        t.check("PERSON@example.com")


def test_a_successful_sign_in_resets_the_count():
    t = LoginThrottle(max_failures=3)
    t.record_failure("a@b.c")
    t.record_failure("a@b.c")
    t.record_success("a@b.c")
    t.record_failure("a@b.c")
    t.check("a@b.c")                                  # only one failure since the reset


def test_other_accounts_are_unaffected_by_a_lockout():
    t = LoginThrottle(max_failures=1)
    t.record_failure("victim@example.com")
    t.check("someone-else@example.com")


def test_lockout_expires(monkeypatch):
    import backend.core.security as sec
    clock = {"t": 0.0}
    monkeypatch.setattr(sec.time, "monotonic", lambda: clock["t"])
    t = LoginThrottle(max_failures=1, lockout_seconds=100)
    t.record_failure("a@b.c")
    with pytest.raises(AuthError):
        t.check("a@b.c")
    clock["t"] = 101
    t.check("a@b.c")


def test_failures_outside_the_window_do_not_count(monkeypatch):
    import backend.core.security as sec
    clock = {"t": 0.0}
    monkeypatch.setattr(sec.time, "monotonic", lambda: clock["t"])
    t = LoginThrottle(max_failures=3, window_seconds=10)
    t.record_failure("a@b.c")
    t.record_failure("a@b.c")
    clock["t"] = 60
    t.record_failure("a@b.c")
    t.check("a@b.c")


# ── sign-in service applies the throttle ────────────────────────────────────

def test_sign_in_service_locks_out_after_five_wrong_passwords(monkeypatch):
    from backend.services import identity

    monkeypatch.setattr(identity, "_customer_throttle", LoginThrottle(max_failures=5))
    monkeypatch.setattr(identity.auth_client, "sign_in",
                        lambda e, p: (_ for _ in ()).throw(AuthError("Invalid email or password.")))
    for _ in range(5):
        with pytest.raises(AuthError, match="Invalid email or password"):
            identity.sign_in_customer("victim@example.com", "guess")
    with pytest.raises(AuthError, match="Too many failed attempts"):
        identity.sign_in_customer("victim@example.com", "the-right-password")   # even a correct one is refused


class _FakeRedis:
    """Just enough of redis-py for the throttle: counters, expiry and delete (expiry is tracked, not simulated)."""

    def __init__(self):
        self.data, self.ttls = {}, {}

    def incr(self, k):
        self.data[k] = int(self.data.get(k, 0)) + 1
        return self.data[k]

    def expire(self, k, s):
        self.ttls[k] = s

    def set(self, k, v, ex=None):
        self.data[k], self.ttls[k] = v, ex

    def ttl(self, k):
        return self.ttls.get(k, -2) if k in self.data else -2

    def delete(self, *keys):
        for k in keys:
            self.data.pop(k, None)
            self.ttls.pop(k, None)


@pytest.mark.unit
def test_redis_throttle_is_shared_between_instances():
    from backend.core.security import RedisLoginThrottle

    shared = _FakeRedis()
    a, b = RedisLoginThrottle(shared, "customer", max_failures=3), RedisLoginThrottle(shared, "customer", max_failures=3)
    for _ in range(3):
        a.record_failure("Sam@Example.com")
    with pytest.raises(AuthError):
        b.check("sam@example.com")
    b.record_success("sam@example.com")
    a.check("sam@example.com")


@pytest.mark.unit
def test_redis_throttle_separates_customer_and_operator_counters():
    from backend.core.security import RedisLoginThrottle

    shared = _FakeRedis()
    customer, operator = RedisLoginThrottle(shared, "customer", max_failures=1), RedisLoginThrottle(shared, "operator", max_failures=1)
    customer.record_failure("x@example.com")
    operator.check("x@example.com")


@pytest.mark.unit
def test_redis_throttle_falls_back_to_a_local_limit_when_redis_is_down():
    from backend.core.security import RedisLoginThrottle

    class Down:
        def __getattr__(self, name):
            raise ConnectionError("redis is down")

    t = RedisLoginThrottle(Down(), "customer", max_failures=2)
    t.check("x@example.com")
    t.record_failure("x@example.com")
    t.record_failure("x@example.com")
    with pytest.raises(AuthError):
        t.check("x@example.com")
