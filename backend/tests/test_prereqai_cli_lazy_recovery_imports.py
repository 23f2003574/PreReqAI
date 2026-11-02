"""`prerequisites` commands do not load the ~250 recovery-decision modules (0.13s of start-up); their names stay importable."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]


def _python(code):
    run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    return run.stdout.strip()


def test_importing_the_cli_and_parsing_prerequisites_loads_no_recovery_modules():
    out = _python("import sys, backend.cli as c; c.build_parser() if hasattr(c, 'build_parser') else None;"
                  "print(sum(m.startswith('backend.agent_') for m in sys.modules))")
    assert out == "0"


def test_the_recovery_names_are_still_importable_from_backend_cli_and_load_on_demand():
    out = _python("import sys, backend.cli as c;"
                  "from backend.cli import READY, HEALTH_HEALTHY, build_recovery_decision_facade, _build_collaborators;"
                  "print(READY == c.READY, callable(build_recovery_decision_facade),"
                  " any(m.startswith('backend.agent_') for m in sys.modules))")
    assert out == "True True True"


def test_an_unknown_attribute_is_still_an_attribute_error():
    assert _python("import backend.cli as c\ntry:\n    c.nope\nexcept AttributeError as e:\n    print('AttributeError')") == "AttributeError"
