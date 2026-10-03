"""`--json` is the machine-readable form of the workflow result: parseable JSON
alone on stdout, stable field names, a non-zero exit on failure, no traceback,
and the human output unchanged when it is not requested."""
import json

import pytest

from backend.api_generation import generate_application
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from test_api_generation_boundary import _draft, _env
from test_api_generation_cli import drafts  # noqa: F401  (fixture)

COMMON = {"status", "source", "stages_completed", "dry_run", "validation", "warnings"}
SUCCESS_KEYS = COMMON | {"draft_id", "endpoint", "output_dir", "files", "openapi_path", "artifact_types"}
FAILURE_KEYS = COMMON | {"failed_stage", "error"}


def _json_run(capsys, *args):
    code = main(["api-generation", "generate", *args, "--json"])
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured  # json.loads proves stdout is exactly one JSON document


def test_successful_output_has_the_stable_field_names(tmp_path, drafts, capsys):  # noqa: F811
    code, data, captured = _json_run(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"))

    assert code == EXIT_OK and set(data) == SUCCESS_KEYS and data["status"] == "success"
    assert captured.err == "" and "Traceback" not in captured.out
    assert isinstance(data["files"], list) and isinstance(data["warnings"], list) and isinstance(data["dry_run"], bool)


@pytest.mark.parametrize(
    "extra,stage",
    [(["--port", "0"], "configuration"), ([], "generation")],
)
def test_failed_output_has_the_stable_failure_fields_and_a_nonzero_exit(tmp_path, drafts, capsys, extra, stage):  # noqa: F811
    draft = drafts[1] if stage == "generation" else drafts[0]

    code, data, captured = _json_run(capsys, "--draft", str(draft), "--output-dir", str(tmp_path / "o"), *extra)

    assert code == EXIT_FAILURE and set(data) == FAILURE_KEYS and data["status"] == "failed"
    assert data["failed_stage"] == stage and set(data["error"]) == {"type", "message"}
    assert "Traceback" not in captured.out and "Traceback" not in captured.err
    assert captured.err.startswith("error: ")  # the human error report still goes to stderr


def test_the_json_result_is_the_workflow_result_serialized_not_a_parallel_model(tmp_path, drafts, capsys):  # noqa: F811
    env = _env()
    _, validated = _draft(env)
    direct = generate_application(env["draft"], validated, tmp_path / "direct").to_dict()
    _, data, _ = _json_run(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "cli"))

    assert set(direct) == {"draft_id", "endpoint", "output_dir", "files", "openapi_path", "dry_run"}
    assert {k: data[k] for k in ("draft_id", "endpoint", "files", "dry_run")} == {k: direct[k] for k in ("draft_id", "endpoint", "files", "dry_run")}
    assert json.loads(json.dumps(direct)) == direct  # nothing needs a custom serializer


def test_dry_run_json_reports_a_dry_run_and_writes_nothing(tmp_path, drafts, capsys):  # noqa: F811
    code, data, _ = _json_run(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"), "--dry-run")

    assert code == EXIT_OK and data["dry_run"] is True and not (tmp_path / "o").exists()


def test_human_output_is_unchanged_without_the_json_option(tmp_path, drafts, capsys):  # noqa: F811
    main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o")])

    lines = capsys.readouterr().out.splitlines()
    assert lines[:6] == [f"[ok] {s}" for s in ("configuration", "preflight", "input", "generation", "validation", "write")]
    assert lines[6] == "Generated POST /add (draft " + json.loads(drafts[0].read_text())["draft_id"] + ")"
    assert lines[-1].startswith("Result: success") and not any(line.lstrip().startswith("{") for line in lines)


def test_check_json_is_parseable_and_healthy_for_a_generated_project(tmp_path, drafts, capsys):  # noqa: F811
    main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"), "-q"])
    capsys.readouterr()

    code = main(["api-generation", "check", str(tmp_path / "o"), "--json"])

    assert code == EXIT_OK and json.loads(capsys.readouterr().out)["status"] == "healthy"
