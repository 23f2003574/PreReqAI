"""The CI workflow runs the PreReqAI release checks on the oldest Python the project declares, so 3.10 support is not just a claim."""
import re
from pathlib import Path

from backend.python_version import MINIMUM

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github" / "workflows" / "prereqai.yml").read_text(encoding="utf-8")


def test_workflow_tests_the_minimum_supported_python():
    versions = re.search(r"python-version:\s*\[([^\]]*)\]", WORKFLOW).group(1)
    assert f'"{MINIMUM[0]}.{MINIMUM[1]}"' in versions, "CI must run the oldest Python the code accepts (backend/python_version.py)"


def test_workflow_runs_the_release_checks_and_the_readme_quickstart():
    assert "python -m pytest -m prereqai backend/tests" in WORKFLOW
    assert "python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf" in WORKFLOW
    assert "pip install -r requirements-dev.txt" in WORKFLOW


def test_readme_names_the_same_minimum_version():
    assert f"Python {MINIMUM[0]}.{MINIMUM[1]} or newer" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_workflow_uses_least_privilege_a_timeout_and_node24_actions():
    assert re.search(r"^permissions:\s*\n\s+contents: read\b", WORKFLOW, re.MULTILINE)
    assert "timeout-minutes:" in WORKFLOW
    # GitHub runs Node 20 actions (checkout@v4, setup-python@v5) on Node 24 with a deprecation warning
    assert "actions/checkout@v4" not in WORKFLOW and "actions/setup-python@v5" not in WORKFLOW


def test_workflow_starts_the_http_server_from_the_runtime_only_install():
    # TestClient-based tests run with the dev requirements; only a real server in the runtime venv catches a missing runtime package
    # (for example python-multipart, which the analyze upload needs, or uvicorn itself).
    step = WORKFLOW.split("README HTTP server with only the runtime requirements", 1)[1]
    assert '"$RUNNER_TEMP/runtime/bin/python" -m uvicorn backend.main:app' in step
    assert "curl -sf http://127.0.0.1:8000/health" in step
    assert "/api/prerequisites/analyze" in step and "examples/prerequisites/sample-paper.pdf" in step
    # it must come after the runtime venv is created and filled, or it would use a venv that does not exist yet
    assert WORKFLOW.index("pip\" install -r requirements.txt") < WORKFLOW.index("README HTTP server with only the runtime requirements")


def test_runtime_requirements_list_what_the_http_server_needs():
    runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for package in ("fastapi", "uvicorn", "python-multipart", "pymupdf", "requests"):
        assert package in runtime, f"{package} is needed to serve the upload endpoint from a runtime-only install"
