"""Every third-party package the PreReqAI runtime imports is declared in requirements.txt (not only pulled in by chance)."""
import ast
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ["backend/main.py", "backend/cli.py", "backend/cli_prerequisites.py", "backend/study_plan_markdown.py",
           "backend/platform/prereqai_platform.py", "backend/session/session_manager.py",
           *sorted(str(path.relative_to(ROOT)) for path in (ROOT / "backend" / "api").glob("*.py"))]
IMPORT_TO_DISTRIBUTION = {"pymupdf": "pymupdf"}  # the import name differs from the PyPI name
FASTAPI_GUARANTEED = {"starlette", "pydantic"}  # hard dependencies of the declared fastapi


def _declared():
    names = set()
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        match = re.match(r"([A-Za-z0-9_.-]+)", line.strip())
        if match and not line.strip().startswith("#"):
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def _third_party_imports():
    found = set()
    for relative in RUNTIME:
        for node in ast.walk(ast.parse((ROOT / relative).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                continue
            found |= {name.split(".")[0] for name in names}
    return {name for name in found if name not in sys.stdlib_module_names and name != "backend"}


def test_every_runtime_import_is_declared():
    declared = _declared()
    missing = sorted(name for name in _third_party_imports() - FASTAPI_GUARANTEED
                     if IMPORT_TO_DISTRIBUTION.get(name, name).lower() not in declared)
    assert not missing, f"imported by the PreReqAI runtime but not in requirements.txt: {missing}"


def test_the_declared_set_includes_the_runtime_basics():
    assert {"pymupdf", "requests", "fastapi", "uvicorn", "python-multipart", "urllib3"} <= _declared()
