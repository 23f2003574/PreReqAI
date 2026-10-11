"""An unsupported Python gets a readable message, and the code base stays within the grammar of the minimum version."""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

from backend.python_version import MINIMUM, check_python_version

BACKEND = Path(__file__).resolve().parents[1]


def test_supported_versions_pass_silently():
    for version in (MINIMUM, (3, 11, 4), (3, 13, 0), (4, 0, 0), None):
        check_python_version(version)


def test_an_old_python_is_refused_with_both_versions_named():
    with pytest.raises(SystemExit) as refused:
        check_python_version((3, 9, 18))
    message = str(refused.value)
    assert "Python 3.10 or newer" in message and "Python 3.9.18" in message and "python3.10 -m venv" in message


def test_the_entrypoints_run_the_check_before_their_heavy_imports():
    for name in ("cli.py", "main.py"):
        source = (BACKEND / name).read_text()
        assert source.index("check_python_version()") < source.index("from backend.api") if name == "main.py" else (
            source.index("check_python_version()") < source.index("from backend.agent_"))


def test_module_imports_cleanly_and_the_cli_still_runs():
    result = subprocess.run([sys.executable, "-m", "backend.cli", "--help"], capture_output=True, text=True, cwd=BACKEND.parent)
    assert result.returncode == 0 and "usage" in result.stdout.lower()


def test_backend_sources_parse_with_the_minimum_python_grammar():
    broken = []
    for path in BACKEND.rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), feature_version=MINIMUM)
        except SyntaxError as error:
            broken.append(f"{path.relative_to(BACKEND)}: {error.msg}")
    assert not broken, broken[:5]
