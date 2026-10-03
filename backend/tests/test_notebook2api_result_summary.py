"""One final, deterministic summary per `api-generation generate` run: --json
carries it (plus the earlier result keys) for success AND failure, and the
human output ends with a single Result line."""
import json

from backend.cli import EXIT_FAILURE, EXIT_OK, main
from test_api_generation_cli import drafts  # noqa: F401  (fixture)

STAGES = ["configuration", "preflight", "input", "generation", "validation", "write"]


def _run(capsys, *args):
    code = main(["api-generation", "generate", *args])
    return code, capsys.readouterr()


def test_successful_json_summary_has_the_complete_deterministic_shape(tmp_path, drafts, capsys):  # noqa: F811
    code, out = _run(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"), "--json")

    summary = json.loads(out.out)
    assert code == EXIT_OK and summary["status"] == "success" and summary["source"] == str(drafts[0])
    assert summary["stages_completed"] == STAGES and summary["validation"] == "passed" and summary["warnings"] == []
    assert summary["artifact_types"] == ["application-source", "container-image", "dependency-manifest", "documentation",
                                         "openapi-contract", "project-configuration", "project-metadata"]
    assert summary["output_dir"] == str((tmp_path / "o").resolve()) and summary["dry_run"] is False
    for key in ("draft_id", "endpoint", "files", "openapi_path"):  # the earlier machine-readable keys are preserved
        assert key in summary
    assert "failed_stage" not in summary and "error" not in summary


def test_the_summary_is_identical_across_runs_apart_from_the_output_location(tmp_path, drafts, capsys):  # noqa: F811
    summaries = []
    for name in ("a", "b"):
        _, out = _run(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / name), "--json")
        data = json.loads(out.out)
        summaries.append({k: v for k, v in data.items() if k not in ("output_dir", "openapi_path")})

    assert summaries[0] == summaries[1]


def test_dry_run_summary_is_marked_and_still_a_success(tmp_path, drafts, capsys):  # noqa: F811
    code, out = _run(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"), "--dry-run", "--json")

    summary = json.loads(out.out)
    assert code == EXIT_OK and summary["status"] == "success" and summary["dry_run"] is True and not (tmp_path / "o").exists()


def test_failed_json_summary_names_the_stage_and_reason_and_never_reports_success(tmp_path, drafts, capsys):  # noqa: F811
    code, out = _run(capsys, "--draft", str(drafts[1]), "--output-dir", str(tmp_path / "o"), "--json")

    summary = json.loads(out.out)
    assert code == EXIT_FAILURE and summary["status"] == "failed" and summary["failed_stage"] == "generation"
    assert summary["stages_completed"] == ["configuration", "preflight", "input"]
    assert summary["error"]["type"] == "DraftNotValidatedError" and summary["validation"] == "not run"
    assert "files" not in summary and "output_dir" not in summary and not (tmp_path / "o").exists()
    assert out.err.startswith("error: generation failed at stage 'generation'")  # the #2 error report is unchanged


def test_an_early_failure_summary_reports_what_completed(tmp_path, capsys):
    code, out = _run(capsys, "--draft", str(tmp_path / "x.json"), "--output-dir", str(tmp_path / "o"), "--port", "0", "--json")

    summary = json.loads(out.out)
    assert code == EXIT_FAILURE and summary["status"] == "failed" and summary["failed_stage"] == "configuration"
    assert summary["stages_completed"] == [] and summary["source"] == str(tmp_path / "x.json")


def test_human_output_ends_with_one_result_line_for_success_and_failure(tmp_path, drafts, capsys):  # noqa: F811
    _, ok = _run(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"), "-q")
    _, bad = _run(capsys, "--draft", str(drafts[1]), "--output-dir", str(tmp_path / "p"), "-q")

    assert ok.out.splitlines()[-1].startswith("Result: success (6 stages completed, validation passed; artifacts: ")
    assert bad.out.splitlines() == ["Result: failed at stage 'generation' (completed: configuration, preflight, input)"]
