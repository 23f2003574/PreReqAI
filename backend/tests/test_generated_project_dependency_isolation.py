"""The generated requirements.txt is derived from the generated project alone:
every line is justified by an import in the generated code or by the server
its Dockerfile runs, nothing comes from PreReqAI's own (development)
requirements, and the result is deterministic, duplicate-free and free of
local paths. The project then imports from an isolated clean copy."""
import ast
import importlib.metadata
import json
import re
import sys

import pytest

from backend.api_generation import generate_requirements
from backend.api_generation.manifest import GENERATED_SPECIFIERS
from backend.cli import EXIT_OK, main
from test_generated_project_clean_build import _clean_copy
from test_generated_project_importability import EXAMPLE, REPO_ROOT, _probe

_REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(>=[0-9][0-9.]*)?$")


def _names(text: str) -> list:
    return [re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0].lower() for line in text.splitlines() if line.strip()]


def _generated_imports(project, package) -> set:
    found = set()
    for source in (project / package).rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Import):
                found |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                found.add(node.module.split(".")[0])
    return found


@pytest.mark.parametrize("extra, package", [((), "app"), (("--project-name", "loan-quote"), "loan_quote")])
def test_manifest_is_exactly_the_generated_imports_plus_the_served_asgi_server(tmp_path, capsys, extra, package):
    project = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"),
                 "--output-dir", str(project), *extra]) == EXIT_OK
    capsys.readouterr()

    imports = _generated_imports(project, package)
    third_party = {m for m in imports if m not in sys.stdlib_module_names and m != package}
    requirements = (project / "requirements.txt").read_text()
    names = _names(requirements)
    server = re.search(r"exec (\w+) " + package + r"\.main:app", (project / "Dockerfile").read_text()).group(1)

    # each requirement is justified by the project itself, and each import is covered
    distributions = importlib.metadata.packages_distributions()
    imported_distributions = {distributions[m][0].lower() for m in third_party}
    assert set(names) == imported_distributions | {server} == {"fastapi", "pydantic", "uvicorn"}
    # deterministic, sorted, duplicate-free, versioned only by the generator's own floors
    assert names == sorted(set(names))
    assert requirements.splitlines() == [f"{n}{GENERATED_SPECIFIERS[n]}" for n in names]
    for line in requirements.splitlines():  # no paths, URLs, editable installs or markers
        assert _REQUIREMENT.match(line), line
    # isolated: the clean declared project imports with nothing from the host
    seen = _probe(_clean_copy(project, tmp_path / "clean"), package)
    assert seen["blocked"] == [] and seen["host_modules"] == []


def test_unrelated_host_dependencies_never_reach_the_generated_manifest(tmp_path, capsys):
    project = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"),
                 "--output-dir", str(project)]) == EXIT_OK
    capsys.readouterr()

    host = set(_names((REPO_ROOT / "requirements.txt").read_text())) | set(
        _names((REPO_ROOT / "requirements-dev.txt").read_text()))
    generated = set(_names((project / "requirements.txt").read_text()))
    unrelated = host - {"fastapi", "pydantic", "uvicorn"}

    assert {"pymupdf", "pdfplumber", "pytest", "requests"} <= unrelated  # the host really has others
    assert generated.isdisjoint(unrelated)
    manifest = json.loads((project / "prereqai-manifest.json").read_text())
    assert [a["path"] for a in manifest["artifacts"] if a["type"] == "dependency-manifest"] == ["requirements.txt"]


def test_requirements_follow_the_code_not_a_fixed_list():
    """Derivation is from the artifact: a project importing only fastapi
    needs no pydantic line, and its own package is never a dependency."""
    only_fastapi = {"svc/main.py": "from fastapi import FastAPI\nfrom svc import helpers\nimport json\n"}
    assert generate_requirements(only_fastapi, also=("uvicorn",)) == "fastapi>=0.115.0\nuvicorn>=0.32.0\n"
    nested = {"svc/main.py": "def f():\n    import pydantic.v1\n    from fastapi.responses import JSONResponse\n"}
    assert generate_requirements(nested) == "fastapi>=0.115.0\npydantic>=2.0\n"
