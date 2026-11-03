"""requirements.txt is installable and sufficient: every third-party package the product's start-up and analysis path
imports is declared, and no declared floor admits a version known not to import on a supported Python."""
import ast
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
# packages installed with a declared one (fastapi depends on both)
VIA_FASTAPI = {"pydantic", "starlette"}
IMPORT_NAME = {"pymupdf": "pymupdf", "python-multipart": "multipart"}
PRODUCT_PATH = ["main.py", "cli.py", "cli_common.py", "cli_prerequisites.py", "study_plan_markdown.py",
                "api", "platform", "pipeline", "ingestion", "parsing", "concepts", "prerequisites", "tutor", "models"]


def _declared():
    names = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        spec = line.split("#")[0].strip()
        if spec:
            names[re.split(r"[<>=!~\[ ]", spec)[0].lower()] = spec
    return names


def _third_party_imports():
    found = set()
    for entry in PRODUCT_PATH:
        base = ROOT / "backend" / entry
        for path in ([base] if base.is_file() else base.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    found.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    return {name for name in found if name not in sys.stdlib_module_names and name != "backend"}


def test_every_third_party_import_of_the_product_path_is_declared():
    declared = {IMPORT_NAME.get(name, name) for name in _declared()}
    undeclared = _third_party_imports() - declared - VIA_FASTAPI

    assert not undeclared, f"imported but not in requirements.txt: {sorted(undeclared)}"


def test_the_urllib3_floor_excludes_releases_that_cannot_be_imported_on_python_3_12_and_later():
    spec = _declared()["urllib3"]
    floor = tuple(int(part) for part in re.search(r">=\s*([\d.]+)", spec).group(1).split("."))

    assert floor >= (1, 26, 5), f"{spec}: urllib3 1.26.0-1.26.4 fail with 'No module named urllib3.packages.six.moves'"
