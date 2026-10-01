import json

import pytest

from backend.api_generation import (
    HEALTHY,
    INCOMPATIBLE,
    INVALID,
    check_generated_project,
    generate_application,
)
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from test_api_generation_boundary import _draft, _env


@pytest.fixture
def project(tmp_path):
    env = _env()
    _, validated = _draft(env)
    return generate_application(env["draft"], validated, tmp_path / "project").output_dir


def test_a_freshly_generated_project_is_healthy(project):
    health = check_generated_project(project)

    assert health.status == HEALTHY and health.healthy and health.findings == []
    assert set(health.checks) == {"manifest", "metadata", "entrypoint", "python", "dependencies", "openapi"}
    assert set(health.checks.values()) == {"passed"}


def test_user_files_and_the_ownership_marker_do_not_affect_health(project):
    (project / "notes.txt").write_text("mine")

    assert check_generated_project(project).healthy


@pytest.mark.parametrize(
    "path,text,failed",
    [
        ("app/main.py", "def broken(:\n", {"python"}),
        ("requirements.txt", "fastapi\n", {"dependencies"}),
        ("openapi.json", "{}\n", {"openapi"}),
        ("prereqai-project.json", '{"generator": "x"}', {"metadata"}),
    ],
)
def test_a_corrupted_artifact_is_invalid_and_names_the_failed_check(project, path, text, failed):
    (project / path).write_text(text)

    health = check_generated_project(project)

    assert health.status == INVALID and not health.healthy
    assert failed <= {name for name, outcome in health.checks.items() if outcome == "failed"}


def test_a_missing_manifest_or_entrypoint_is_invalid(project):
    (project / "prereqai-manifest.json").unlink()
    (project / "app" / "main.py").unlink()

    health = check_generated_project(project)

    assert health.status == INVALID and {"manifest", "entrypoint"} <= {n for n, o in health.checks.items() if o == "failed"}


def test_a_project_from_another_contract_version_is_incompatible_not_merely_invalid(project):
    metadata = json.loads((project / "prereqai-project.json").read_text())
    (project / "prereqai-project.json").write_text(json.dumps({**metadata, "contract_version": 99}))

    health = check_generated_project(project)

    assert health.status == INCOMPATIBLE and health.checks["metadata"] == "failed"
    assert "INCOMPATIBLE_PROJECT" in {f["category"] for f in health.findings}


def test_a_manifest_from_another_manifest_version_is_incompatible(project):
    manifest = json.loads((project / "prereqai-manifest.json").read_text())
    (project / "prereqai-manifest.json").write_text(json.dumps({**manifest, "manifest_version": 2}))

    assert check_generated_project(project).status == INCOMPATIBLE


def test_a_missing_directory_is_invalid_without_a_traceback(tmp_path):
    health = check_generated_project(tmp_path / "nope")

    assert health.status == INVALID and health.findings[0]["category"] == "NOT_A_PROJECT"


def test_cli_reports_health_and_the_exit_code(project, tmp_path, capsys):
    assert main(["api-generation", "check", str(project)]) == EXIT_OK
    assert "Project health: HEALTHY" in capsys.readouterr().out

    assert main(["api-generation", "check", str(project), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "healthy"

    (project / "app" / "main.py").write_text("def broken(:\n")
    assert main(["api-generation", "check", str(project)]) == EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Project health: INVALID" in out and "python: failed" in out and "SYNTAX_ERROR" in out
