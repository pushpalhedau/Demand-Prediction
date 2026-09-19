import uuid

import pytest

from backend.core.request_context import tenant_context
from backend.ml.artifacts import ArtifactError, artifact_exists, load_artifact, model_dir, save_artifact


@pytest.fixture(autouse=True)
def _model_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "a-secret-that-is-long-enough-for-hmac-0123456789")


def _dir():
    return model_dir("xgboost", uuid.uuid4())


def test_a_saved_artifact_round_trips():
    d = _dir()
    save_artifact(d, "model", {"weights": [1, 2, 3]})
    assert load_artifact(d, "model") == {"weights": [1, 2, 3]}


def test_a_tampered_artifact_is_refused_before_it_is_unpickled():
    d = _dir()
    save_artifact(d, "model", {"ok": True})
    path = d / "model.pkl"
    blob = bytearray(path.read_bytes())
    blob[-3] ^= 0xFF
    path.write_bytes(bytes(blob))
    with pytest.raises(ArtifactError, match="failed verification"):
        load_artifact(d, "model")


def test_a_malicious_pickle_never_executes(tmp_path):
    """The classic attack: a pickle whose __reduce__ runs a command. It must be rejected, not run."""
    marker = tmp_path / "pwned"
    import pickle

    class Evil:
        def __reduce__(self):
            return (marker.write_text, ("owned",))

    d = _dir()
    (d / "model.pkl").write_bytes(b"0" * 64 + b"\n" + pickle.dumps(Evil()))
    with pytest.raises(ArtifactError):
        load_artifact(d, "model")
    assert not marker.exists()


def test_an_unsigned_legacy_file_is_refused():
    d = _dir()
    import pickle
    (d / "model.pkl").write_bytes(pickle.dumps({"legacy": True}))
    with pytest.raises(ArtifactError):
        load_artifact(d, "model")


def test_a_file_signed_with_a_different_key_is_refused(monkeypatch):
    d = _dir()
    save_artifact(d, "model", {"ok": True})
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "a-completely-different-secret-value-0123456789")
    with pytest.raises(ArtifactError):
        load_artifact(d, "model")


def test_missing_artifact_says_it_is_not_trained():
    with pytest.raises(ArtifactError, match="not been trained"):
        load_artifact(_dir(), "nope")


def test_each_tenant_has_its_own_directory():
    a, b = uuid.uuid4(), uuid.uuid4()
    with tenant_context(a):
        da = model_dir("clustering")
    with tenant_context(b):
        db = model_dir("clustering")
    assert da != db and str(a) in str(da) and str(b) in str(db)
    save_artifact(da, "m", 1)
    assert artifact_exists("clustering", a, "m") and not artifact_exists("clustering", b, "m")


def test_overwriting_leaves_no_temp_files_behind():
    d = _dir()
    for i in range(3):
        save_artifact(d, "model", i)
    assert [p.name for p in d.iterdir()] == ["model.pkl"]
