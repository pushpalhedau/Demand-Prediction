"""
Architecture rules, enforced. These fail the build when a layer boundary is crossed, which is what keeps
the frontend from ever holding database access or another tenant's data.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Backend packages by layer: a package may import only from its own layer or LOWER ones.
LAYERS = {
    "core": 0,
    "db": 1,
    "repositories": 2, "auth": 2,
    "analytics": 3,
    "sentiment": 4,
    "ml": 5,
    "ingestion": 6,
    "tenancy": 7,
    "services": 8,
}
TOP_LEVEL_BACKEND_MODULES = {"cli"}     # entry points may use anything in the backend

# The ONLY backend modules the frontend may import.
FRONTEND_MAY_IMPORT = ("backend.services", "backend.core.formatting", "backend.core.request_context",
                       "backend.core.errors")
FRONTEND_FORBIDDEN_THIRD_PARTY = ("sqlalchemy", "psycopg2", "redis", "rq", "jwt")


def _py_files(base: str):
    return [p for p in (ROOT / base).rglob("*.py") if "__pycache__" not in p.parts]


def _imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.module, node.lineno))
            found.extend((f"{node.module}.{a.name}", node.lineno) for a in node.names)
        elif isinstance(node, ast.Import):
            found.extend((a.name, node.lineno) for a in node.names)
    return found


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_backend_never_imports_the_web_framework_or_the_frontend():
    bad = [f"{_rel(p)}:{line} imports {mod}" for p in _py_files("backend") for mod, line in _imports(p)
           if mod.split(".")[0] in ("streamlit", "frontend")]
    assert not bad, "\n".join(bad)


def test_frontend_reaches_the_backend_only_through_services():
    bad = []
    for p in _py_files("frontend"):
        for mod, line in _imports(p):
            top = mod.split(".")[0]
            if top in FRONTEND_FORBIDDEN_THIRD_PARTY:
                bad.append(f"{_rel(p)}:{line} imports {mod}")
            if mod.startswith("backend") and not mod.startswith(FRONTEND_MAY_IMPORT) and mod != "backend":
                bad.append(f"{_rel(p)}:{line} imports {mod}")
    assert not bad, "frontend must go through backend.services:\n" + "\n".join(sorted(set(bad)))


def test_backend_layers_only_depend_downwards():
    bad = []
    for p in _py_files("backend"):
        parts = p.relative_to(ROOT).parts            # ("backend", "<pkg>", ...)
        pkg = parts[1] if len(parts) > 2 else parts[1].removesuffix(".py")
        if pkg in TOP_LEVEL_BACKEND_MODULES or pkg not in LAYERS:
            continue
        for mod, line in _imports(p):
            segs = mod.split(".")
            if segs[0] == "backend" and len(segs) > 1 and segs[1] in LAYERS and LAYERS[segs[1]] > LAYERS[pkg]:
                bad.append(f"{_rel(p)}:{line} ({pkg}) imports upward: {mod}")
    assert not bad, "\n".join(sorted(set(bad)))


def test_every_backend_package_is_classified():
    """A new backend package must be given a layer, so the rule above keeps covering it."""
    packages = {p.name for p in (ROOT / "backend").iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert packages <= set(LAYERS), f"unclassified backend packages: {sorted(packages - set(LAYERS))}"


@pytest.mark.parametrize("base", ["backend", "frontend"])
def test_every_package_directory_has_an_init(base):
    missing = [d.relative_to(ROOT).as_posix() for d in (ROOT / base).rglob("*")
               if d.is_dir() and d.name != "__pycache__" and any(d.glob("*.py")) and not (d / "__init__.py").exists()]
    assert not missing, missing
