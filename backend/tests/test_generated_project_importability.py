"""The generated project imports and runs on its own: from its output
directory, in an isolated interpreter (`python -I`: no PYTHONPATH, no user
site, no current directory), with the PreReqAI source tree made unimportable.
Any import of the host repository -- the `backend` package or any module
whose file lives under the repository root -- fails the check."""
import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.cli import EXIT_OK, main

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "api-generation"

# Runs inside the isolated interpreter. argv: project dir, package, repo root, example request body.
_PROBE = r'''
import importlib, importlib.abc, json, sys
from pathlib import Path

project, package, repo_root, body = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve(), json.loads(sys.argv[4])
blocked = []

class HostRepositoryGuard(importlib.abc.MetaPathFinder):
    """Refuses the host repository's packages, whatever sys.path says."""
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {"backend", "frontend", "examples"}:
            blocked.append(name)
            raise ImportError(f"generated project imported the host repository module {name!r}")
        return None

sys.meta_path.insert(0, HostRepositoryGuard())
sys.path = [str(project)] + [p for p in sys.path if p and not Path(p).resolve().is_relative_to(repo_root)]

app_module = importlib.import_module(f"{package}.main")
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = app_module.app
models = sorted(n for n, v in vars(app_module).items() if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == app_module.__name__)
response = TestClient(app).post(next(r.path for r in app.routes if getattr(r, "methods", None) and "POST" in r.methods), json=body)

host = sorted(
    name for name, module in list(sys.modules.items())
    if getattr(module, "__file__", None) and Path(module.__file__).resolve().is_relative_to(repo_root)
    and not Path(module.__file__).resolve().is_relative_to(project)
)
print(json.dumps({
    "is_fastapi": isinstance(app, FastAPI), "module_file": str(Path(app_module.__file__).resolve()),
    "models": models, "status": response.status_code, "result": response.json(),
    "openapi_paths": sorted(app.openapi()["paths"]), "blocked": blocked, "host_modules": host,
}))
'''


def _generate(tmp_path, capsys, *extra):
    out = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"),
                 "--output-dir", str(out), *extra]) == EXIT_OK
    capsys.readouterr()
    return out


def _probe(project: Path, package: str) -> dict:
    example = json.loads((EXAMPLE / "draft.json").read_text())["examples"][0]
    run = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE, str(project), package, str(REPO_ROOT), json.dumps(example["input"])],
        cwd=project, capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == 0, run.stderr
    seen = json.loads(run.stdout)
    assert seen["result"] == example["output"]
    return seen


def _imported_top_level_modules(project: Path, package: str) -> set:
    names = set()
    for source in sorted((project / package).glob("*.py")):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Import):
                names |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("extra, package", [((), "app"), (("--project-name", "loan-quote"), "loan_quote")])
def test_generated_project_imports_standalone_outside_the_repository(tmp_path, capsys, extra, package):
    project = _generate(tmp_path, capsys, *extra)
    assert not project.resolve().is_relative_to(REPO_ROOT)

    seen = _probe(project, package)

    assert seen["is_fastapi"] and seen["status"] == 200
    assert Path(seen["module_file"]) == (project / package / "main.py").resolve()  # its own module, not a copy elsewhere
    assert seen["models"] == ["PostLoanQuoteRequest", "PostLoanQuoteRequestApplicant", "PostLoanQuoteResponse"]
    assert seen["openapi_paths"] == ["/loan-quote"]
    assert seen["blocked"] == [] and seen["host_modules"] == []


def test_committed_example_imports_standalone_even_inside_the_repository():
    """The committed reference project sits inside the repository, where an
    accidental `import backend...` would silently succeed; the guard and the
    host-module scan must still find nothing."""
    seen = _probe(EXAMPLE / "generated", "app")
    assert seen["blocked"] == [] and seen["host_modules"] == []


def test_generated_imports_are_exactly_stdlib_plus_the_generated_requirements(tmp_path, capsys):
    project = _generate(tmp_path, capsys)
    requirements = {
        line.split(">")[0].split("=")[0].split("<")[0].strip().lower()
        for line in (project / "requirements.txt").read_text().splitlines() if line.strip()
    }
    imported = _imported_top_level_modules(project, "app")

    third_party = {name for name in imported if name not in sys.stdlib_module_names}
    assert "backend" not in imported and third_party <= requirements
    assert third_party == {"fastapi", "pydantic"} and "uvicorn" in requirements  # uvicorn runs it, nothing imports it


def test_the_isolation_guard_catches_a_host_repository_import(tmp_path, capsys):
    """Regression for the boundary itself: a generated module that reaches
    into the host repository must fail the probe, not pass silently."""
    project = _generate(tmp_path, capsys)
    main_py = project / "app" / "main.py"
    main_py.write_text("import backend.api_generation\n" + main_py.read_text())

    example = json.loads((EXAMPLE / "draft.json").read_text())["examples"][0]
    run = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE, str(project), "app", str(REPO_ROOT), json.dumps(example["input"])],
        cwd=project, capture_output=True, text=True, timeout=60,
    )
    assert run.returncode != 0 and "host repository module 'backend'" in run.stderr
