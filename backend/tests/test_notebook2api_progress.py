"""Stage progress for `api-generation generate`: human mode prints one line per
stage on stdout, --json and --quiet print none, a failure shows the failed
stage, and progress never changes results."""
import json
from dataclasses import asdict

from backend.api_generation import generate_application
from backend.cli import EXIT_INVALID_INPUT, EXIT_OK, main
from test_api_generation_boundary import _draft, _env
from test_api_generation_cli import drafts  # noqa: F401  (fixture)

STAGES = ["configuration", "preflight", "input", "generation", "validation", "write"]


def _stages(text):
    return [line for line in text.splitlines() if line.startswith("[")]


def test_each_stage_reports_ok_in_pipeline_order(tmp_path, drafts, capsys):  # noqa: F811
    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o")])

    out = capsys.readouterr().out
    assert code == EXIT_OK and _stages(out) == [f"[ok] {stage}" for stage in STAGES]
    assert "Generated POST /add" in out  # the existing summary is unchanged


def test_dry_run_says_nothing_was_written(tmp_path, drafts, capsys):  # noqa: F811
    main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"), "--dry-run"])

    assert _stages(capsys.readouterr().out)[-1] == "[ok] write (dry run: nothing written)" and not (tmp_path / "o").exists()


def test_json_and_quiet_modes_print_no_progress(tmp_path, drafts, capsys):  # noqa: F811
    assert main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "a"), "--json"]) == EXIT_OK
    out = capsys.readouterr().out
    assert json.loads(out)["endpoint"] == "POST /add" and _stages(out) == []  # stdout is still pure JSON

    assert main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "b"), "-q"]) == EXIT_OK
    assert _stages(capsys.readouterr().out) == []


def test_a_failure_marks_the_failed_stage_and_stops_there(tmp_path, drafts, capsys):  # noqa: F811
    code = main(["api-generation", "generate", "--draft", str(drafts[1]), "--output-dir", str(tmp_path / "o")])

    captured = capsys.readouterr()
    assert code == EXIT_INVALID_INPUT
    assert _stages(captured.out) == ["[ok] configuration", "[ok] preflight", "[ok] input", "[failed] generation"]
    assert captured.err.startswith("error: generation failed at stage 'generation'")  # error report unchanged


def test_an_early_failure_stops_before_later_stages(tmp_path, capsys):
    code = main(["api-generation", "generate", "--draft", str(tmp_path / "x.json"), "--output-dir", str(tmp_path / "o"), "--port", "0"])

    assert code == EXIT_INVALID_INPUT and _stages(capsys.readouterr().out) == ["[failed] configuration"]


def test_progress_callback_observes_only_and_cannot_change_the_result(tmp_path):
    env = _env()
    _, validated = _draft(env)
    seen = []

    observed = generate_application(env["draft"], validated, tmp_path / "a", progress=lambda s, st: seen.append((s, st)))
    plain = generate_application(env["draft"], validated, tmp_path / "b")

    def broken(stage, status):
        raise RuntimeError("reporter bug")

    resilient = generate_application(env["draft"], validated, tmp_path / "c", progress=broken)

    assert seen == [("preflight", "ok"), ("generation", "ok"), ("validation", "ok"), ("write", "ok")]
    assert observed.files == plain.files == resilient.files
    assert asdict(observed)["draft_id"] == asdict(resilient)["draft_id"]
