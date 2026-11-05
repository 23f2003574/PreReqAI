"""The shipped tree (`git archive HEAD`) must not import a `backend` module that is not in it: a module that exists only in
a working tree (uncommitted or git-ignored) makes the release fail on first use, far from the omission. Static, offline,
and independent of the installed environment (it reads the archive's file names and sources, it imports nothing)."""
import ast
import io
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def shipped():
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout: the release artifact cannot be exported")
    data = subprocess.run(["git", "archive", "--format=tar", "HEAD", "backend"], cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as bundle:
        return {member.name: bundle.extractfile(member).read() for member in bundle.getmembers() if member.isfile()}


def _exists(files, module):
    path = module.replace(".", "/")
    return f"{path}.py" in files or f"{path}/__init__.py" in files or any(name.startswith(f"{path}/") for name in files)


def missing_internal_imports(files):
    """(file, imported module) for every absolute `backend...` import in the shipped sources that names nothing shipped."""
    problems = []
    for name, source in files.items():
        if not name.endswith(".py") or name.startswith("backend/tests/"):
            continue
        for node in ast.walk(ast.parse(source, filename=name)):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            problems += [(name, module) for module in modules if module.split(".")[0] == "backend" and not _exists(files, module)]
    return problems


def test_every_internal_import_in_the_shipped_tree_resolves_inside_it(shipped):
    assert any(name.endswith(".py") for name in shipped)
    assert missing_internal_imports(shipped) == []


def test_the_check_catches_an_import_of_a_module_that_was_not_shipped():
    files = {"backend/a.py": b"import backend.b\nfrom backend.c import thing\nfrom backend.pkg.mod import x\nimport os\n",
             "backend/b.py": b"", "backend/pkg/__init__.py": b""}
    assert missing_internal_imports(files) == [("backend/a.py", "backend.c"), ("backend/a.py", "backend.pkg.mod")]
