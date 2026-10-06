"""Installability guard for the documented install path (`pip install -r
requirements.txt`, there is no package metadata): every third-party module the
runtime code imports unconditionally is provided by a requirements.txt entry,
every requirement is installed, and the documented entry points start in a
fresh interpreter from the repository root."""
import ast
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIRS = ("backend", "frontend")
FIRST_PARTY = {"backend", "frontend", "src"}
# import name -> requirements.txt distribution that provides it
PROVIDED_BY = {"fitz": "pymupdf", "pymupdf": "pymupdf", "pdfplumber": "pdfplumber", "fastapi": "fastapi",
               "starlette": "fastapi", "pydantic": "fastapi", "uvicorn": "uvicorn", "requests": "requests",
               "urllib3": "requests", "multipart": "python-multipart"}


def _requirements():
    names = set()
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(re.split(r"[<>=!~\[; ]", line, 1)[0].lower())
    return names


def _guarded(tree):
    """Modules imported inside a `try:` (optional integrations such as openai)."""
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for inner in node.body:
                for sub in ast.walk(inner):
                    if isinstance(sub, ast.Import):
                        guarded |= {alias.name.split(".")[0] for alias in sub.names}
                    elif isinstance(sub, ast.ImportFrom) and sub.module and sub.level == 0:
                        guarded.add(sub.module.split(".")[0])
    return guarded


def _unconditional_third_party_imports():
    found = {}
    for directory in RUNTIME_DIRS:
        for path in (ROOT / directory).rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            optional = _guarded(tree)
            for node in ast.walk(tree):
                names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                         else [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                         else [])
                for name in names:
                    top = name.split(".")[0]
                    if top not in sys.stdlib_module_names and top not in FIRST_PARTY and top not in optional:
                        found.setdefault(top, str(path.relative_to(ROOT)))
    return found


def test_every_unconditional_runtime_import_is_provided_by_requirements_txt():
    requirements = _requirements()
    missing = {module: where for module, where in _unconditional_third_party_imports().items()
               if PROVIDED_BY.get(module) not in requirements}
    assert not missing, f"runtime imports with no requirements.txt entry: {missing}"


def test_every_requirement_is_installed():
    absent = []
    for name in _requirements():
        try:
            metadata.version(name)
        except metadata.PackageNotFoundError:
            absent.append(name)
    assert not absent, f"pip install -r requirements.txt did not provide: {absent}"


def test_documented_entry_points_start_in_a_fresh_interpreter():
    cli = subprocess.run([sys.executable, "-m", "backend.cli", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert cli.returncode == 0 and "prerequisites" in cli.stdout, cli.stderr

    app = subprocess.run([sys.executable, "-c", "from backend.main import app; print(app.title)"],
                         cwd=ROOT, capture_output=True, text=True)
    assert app.returncode == 0 and app.stdout.strip() == "PreReqAI", app.stderr
