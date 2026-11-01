"""`--version` and the `prerequisites` commands do not load the API generator, draft and LLM packages (about 0.2s of start-up);
the api-generation names stay importable from backend.cli and its commands still run."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
HEAVY = "('backend.api_generation', 'backend.api_documentation_draft', 'backend.llm')"


def _python(code):
    run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    return run.stdout.strip()


def test_importing_the_cli_and_building_its_parser_loads_no_generator_modules():
    out = _python(f"import sys, backend.cli as c; c._build_parser(); print(any(m.startswith({HEAVY}) for m in sys.modules))")
    assert out == "False"


def test_the_api_generation_names_are_still_importable_and_load_on_demand():
    out = _python("import sys; from backend.cli import EXIT_INVALID_INPUT, EXIT_GENERATION_FAILED, _load_draft, run_api_generation_check;"
                  f"print(EXIT_INVALID_INPUT, EXIT_GENERATION_FAILED, callable(run_api_generation_check), any(m.startswith({HEAVY}) for m in sys.modules))")
    assert out == "3 4 True True"


def test_the_api_generation_commands_still_dispatch(tmp_path):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "api-generation", "check", str(tmp_path / "missing")],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode != 0 and "Traceback" not in run.stderr
    help_run = subprocess.run([sys.executable, "-m", "backend.cli", "api-generation", "--help"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert help_run.returncode == 0 and "generate" in help_run.stdout and "check" in help_run.stdout
