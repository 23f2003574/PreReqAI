"""Release readiness for the Notebook2API workflow. The repository's only test
entrypoint is pytest, so this is one module: it exercises the primary CLI as a
real process (reachability, success, JSON, exit statuses, unsafe output and
configuration rejected before generation), checks that the committed example
stays usable, and re-runs the integration regression matrix. Run it with:

    python -m pytest backend/tests/test_notebook2api_release_readiness.py
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DRAFT = ROOT / "examples" / "api-generation" / "draft.json"
RELEASE_PATH_TESTS = (
    "test_notebook2api_regression_matrix.py", "test_notebook2api_exit_codes.py", "test_notebook2api_json_output.py",
    "test_notebook2api_output_preflight.py", "test_notebook2api_config_validation.py", "test_notebook2api_input_validation.py",
    "test_notebook2api_error_surface.py", "test_notebook2api_result_summary.py", "test_notebook2api_cli_help.py",
    "test_api_generation_example.py", "test_generated_project_release_smoke.py", "test_api_generation_release_checklist.py",
)


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "backend.cli", *args], cwd=ROOT, capture_output=True, text=True)


def test_the_release_path_test_modules_are_all_present():
    missing = [name for name in RELEASE_PATH_TESTS if not (Path(__file__).parent / name).is_file()]
    assert missing == []


def test_primary_workflow_runs_end_to_end_as_a_real_process(tmp_path):
    help_run = _cli("api-generation", "--help")
    assert help_run.returncode == 0 and "generate" in help_run.stdout and "check" in help_run.stdout  # reachable

    out = tmp_path / "project"
    generated = _cli("api-generation", "generate", "--draft", str(EXAMPLE_DRAFT), "--output-dir", str(out), "--json")
    summary = json.loads(generated.stdout)  # valid JSON
    assert generated.returncode == 0 and summary["status"] == "success" and summary["validation"] == "passed"
    assert summary["endpoint"] == "POST /loan-quote" and all((out / f).is_file() for f in summary["files"])

    checked = _cli("api-generation", "check", str(out), "--json")
    assert checked.returncode == 0 and json.loads(checked.stdout)["status"] == "healthy"  # generated artifacts validate


@pytest.mark.parametrize(
    "extra,code,stage",
    [(["--port", "0"], 3, "configuration"), (["--base-image", "Not An Image"], 3, "configuration")],
)
def test_unsafe_configuration_is_rejected_before_generation_with_the_documented_exit_status(tmp_path, extra, code, stage):
    run = _cli("api-generation", "generate", "--draft", str(EXAMPLE_DRAFT), "--output-dir", str(tmp_path / "o"), "--json", *extra)

    summary = json.loads(run.stdout)
    assert run.returncode == code and summary["failed_stage"] == stage and "generation" not in summary["stages_completed"]
    assert not (tmp_path / "o").exists()


def test_an_unsafe_output_directory_is_rejected_and_left_untouched(tmp_path):
    (tmp_path / "Dockerfile").write_text("the user's own")

    run = _cli("api-generation", "generate", "--draft", str(EXAMPLE_DRAFT), "--output-dir", str(tmp_path), "--json")

    assert run.returncode == 3 and json.loads(run.stdout)["status"] == "failed"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Dockerfile"] and (tmp_path / "Dockerfile").read_text() == "the user's own"


def test_the_committed_example_project_is_still_healthy():
    run = _cli("api-generation", "check", str(ROOT / "examples" / "api-generation" / "generated"), "--json")

    assert run.returncode == 0 and json.loads(run.stdout)["status"] == "healthy"


def test_the_integration_regression_matrix_passes():
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(Path(__file__).parent / "test_notebook2api_regression_matrix.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stdout[-1500:]
