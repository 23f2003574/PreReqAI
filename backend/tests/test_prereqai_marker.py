import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _collected(*args):
    run = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
                         cwd=ROOT, capture_output=True, text=True, timeout=300)
    return {line.split("::")[0] for line in run.stdout.splitlines() if "::" in line}


def test_the_prereqai_marker_selects_exactly_the_release_check_files():
    expected = {f"backend/tests/{path.name}" for path in (ROOT / "backend/tests").glob("test_prereqai_*.py")}
    expected.add("backend/tests/test_prerequisite_endpoint.py")
    assert _collected("-m", "prereqai", "backend/tests/test_prereqai_marker.py", "backend/tests/test_prereqai_cli_ask.py",
                      "backend/tests/test_prerequisite_endpoint.py", "backend/tests/test_api_generation_cli.py") <= expected
    assert _collected("-m", "prereqai") == expected
