"""The test suite does not depend on the directory pytest was started from."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_quickstart_tests_pass_when_pytest_is_started_outside_the_repository(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:warnings", "-p", "no:cacheprovider",
         str(ROOT / "backend" / "tests" / "test_prereqai_known_keeps_studied.py"),
         str(ROOT / "backend" / "tests" / "test_prereqai_quickstart.py")],
        cwd=tmp_path, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-500:]
