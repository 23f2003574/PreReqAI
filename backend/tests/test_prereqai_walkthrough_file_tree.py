"""The generated-project tree in docs/api-generation-walkthrough.md lists exactly the files the committed example
contains, hidden ones included, so a reader's `ls -a` of a generated project matches the documentation."""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples/api-generation/generated"


def _documented_files():
    text = (ROOT / "docs/api-generation-walkthrough.md").read_text()
    tree = re.search(r"```\n/tmp/loan-quote-api/\n(.*?)```", text, re.S).group(1)
    return {match.group(1) for match in re.finditer(r"[├└│ ]+── ([^\s/]+)(?!/)\s*(?:#|$)", tree, re.M)}


def test_the_documented_project_tree_matches_the_committed_example_files():
    on_disk = {path.name for path in EXAMPLE.rglob("*") if path.is_file() and "__pycache__" not in path.parts}

    assert _documented_files() == on_disk
