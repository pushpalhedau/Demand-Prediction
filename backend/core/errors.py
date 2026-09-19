"""Exception types shared across the backend. Messages on AppError subclasses are safe to show to users."""


class AppError(Exception):
    """Base class for expected, user-actionable failures. `str(e)` is safe to display."""


class TenantNotSet(RuntimeError):
    """A tenant-scoped operation ran with no tenant in scope (a programming error, never user-facing)."""


class AuthError(AppError):
    """Sign-in, token or authorisation failure."""


class IngestError(AppError):
    """An uploaded file or its mapping cannot be imported."""


class InvalidSetting(AppError, ValueError):
    """A tenant setting failed validation."""
