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


def test_workflow_runs_every_test_command_of_the_release_checklist():
    # docs/release-checklist.md step 3 lists the release checks; a command missing from CI lets a release blocker pass unnoticed
    checklist = (ROOT / "docs/release-checklist.md").read_text(encoding="utf-8")
    commands = [line.split("#")[0].strip() for line in checklist.splitlines() if line.strip().startswith("python -m pytest")]
    assert len(commands) >= 2
    for command in commands:
        targets = re.findall(r"backend/tests/\S+", command) + (["-m prereqai"] if "-m prereqai" in command else [])
        assert targets, command
        for target in targets:
            assert target in WORKFLOW, f"CI does not run `{target}` from the release checklist command: {command}"


def test_workflow_runs_every_documented_command_group_from_the_runtime_only_install():
    # ask / api-generation / recovery-decision are imported lazily per command: with the dev requirements installed (pytest,
    # httpx2) a package missing from requirements.txt that only one of them needs would pass every other step.
    step = WORKFLOW.split("Other documented CLI commands with only the runtime requirements", 1)[1]
    for command in ("--version", "--help", "prerequisites ask examples/prerequisites/sample-paper.pdf",
                    "api-generation generate --draft examples/api-generation/draft.json", "api-generation check",
                    "recovery-decision readiness", "--tree --resources --plan-file", "--resume"):
        assert command in step, command
    assert 'PY="$RUNNER_TEMP/runtime/bin/python"' in step  # the runtime venv, not the dev environment
    assert WORKFLOW.index("install -r requirements.txt") < WORKFLOW.index("Other documented CLI commands")
