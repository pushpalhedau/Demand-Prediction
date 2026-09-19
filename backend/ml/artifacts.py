"""
Signed, per-tenant storage for trained model artifacts.

Loading a pickle runs code, so a model file that someone could tamper with (a shared volume, a backup
restore, a compromised worker) would be remote code execution in the web process. Every artifact is
therefore stored as `<HMAC-SHA256 hex>\\n<pickle bytes>` and the signature is verified BEFORE the bytes are
unpickled. A file that is unsigned, altered, or signed with a different key is refused. Each write is a
single atomic file replace, so a reader never sees a half-written artifact.

Layout:  <MODEL_DIR>/<kind>/<tenant_id>/<name>.pkl
"""
from __future__ import annotations

import hashlib
import hmac
import os
import pickle  # noqa: S403 - unpickling happens only after the HMAC below has been verified
import tempfile
from pathlib import Path
from typing import Any

from backend.core.config import get_settings
from backend.core.errors import AppError
from backend.core.request_context import require_tenant_id

_SIG_HEX_LEN = 64


class ArtifactError(AppError):
    """A model artifact is missing, unsigned, or failed verification."""


def _signature(payload: bytes) -> bytes:
    return hmac.new(get_settings().model_signing_key, payload, hashlib.sha256).hexdigest().encode()


def model_dir(kind: str, tenant_id: Any = None) -> Path:
    """Directory for one tenant's artifacts of a kind (created on demand). Defaults to the active tenant."""
    tenant = tenant_id if tenant_id is not None else require_tenant_id()
    directory = get_settings().model_dir / kind / str(tenant)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def artifact_exists(kind: str, tenant_id: Any, name: str) -> bool:
    return (get_settings().model_dir / kind / str(tenant_id) / f"{name}.pkl").exists()


def save_artifact(directory: Path, name: str, obj: Any) -> None:
    payload = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    blob = _signature(payload) + b"\n" + payload
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
        os.replace(tmp, directory / f"{name}.pkl")
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_artifact(directory: Path, name: str) -> Any:
    path = directory / f"{name}.pkl"
    try:
        blob = path.read_bytes()
    except FileNotFoundError as e:
        raise ArtifactError(f"Model artifact '{name}' has not been trained yet.") from e
    signature, sep, payload = blob.partition(b"\n")
    if not sep or len(signature) != _SIG_HEX_LEN or not hmac.compare_digest(signature, _signature(payload)):
        raise ArtifactError(f"Model artifact '{name}' failed verification (unsigned or altered). Retrain the models.")
    return pickle.loads(payload)  # noqa: S301  # nosec B301 - signature verified above
