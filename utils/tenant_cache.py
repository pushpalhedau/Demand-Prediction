import functools

import streamlit as st

from database.tenant_context import require_tenant_id


def tenant_cache_data(ttl=None, show_spinner=False):
    """
    st.cache_data, but the active tenant is part of the cache key.

    Plain st.cache_data is process-wide: a zero-argument loader cached for one
    tenant would be served to every other tenant. The key param is deliberately
    NOT underscore-prefixed, because Streamlit skips hashing underscore params.
    """
    def decorator(fn):
        def keyed(tenant_key, *args, **kwargs):
            return fn(*args, **kwargs)

        keyed.__name__ = fn.__name__
        keyed.__qualname__ = fn.__qualname__
        keyed.__module__ = fn.__module__
        cached = st.cache_data(ttl=ttl, show_spinner=show_spinner)(keyed)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return cached(str(require_tenant_id()), *args, **kwargs)

        wrapper.clear = cached.clear
        return wrapper
    return decorator
