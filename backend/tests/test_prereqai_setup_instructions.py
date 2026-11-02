"""The setup instructions work on the platforms a new developer uses: both activation commands are documented, and everything the
quickstart tells a new user to run or install exists in the checkout (the environment folder it creates is git-ignored)."""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text()
QUICKSTART = README.split("## Quickstart", 1)[1].split("\n## ", 1)[0]


def test_quickstart_documents_activation_for_posix_and_windows():
    assert "source .venv/bin/activate" in QUICKSTART
    assert ".venv\\Scripts\\activate" in QUICKSTART


def test_every_file_the_quickstart_names_exists():
    first_steps = QUICKSTART.split("```bash", 2)[1].split("```", 1)[0]  # the setup block; later examples use placeholder names such as paper.pdf
    named = re.findall(r"(?:-r |analyze )([\w./-]+\.(?:txt|pdf))", first_steps)
    assert {"requirements.txt", "examples/prerequisites/sample-paper.pdf"} <= set(named)
    assert all((ROOT / path).is_file() for path in named), named


def test_the_environment_folder_the_quickstart_creates_is_git_ignored():
    assert ".venv/" in (ROOT / ".gitignore").read_text().splitlines()
