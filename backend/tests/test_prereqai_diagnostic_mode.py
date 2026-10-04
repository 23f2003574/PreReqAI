"""Opt-in diagnostics for the PreReqAI analysis workflow: `prerequisites analyze
--diagnose` (and platform.analyze(..., diagnostics=True)) report stage
durations, completed/failed stages, warnings, status and run statistics; normal
runs are unchanged."""
import json

import fitz
from fastapi.testclient import TestClient

from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.main import app
from backend.platform import platform

DIAGNOSTIC_KEYS = {"status", "stage", "completed_stages", "failed_after", "stage_seconds", "total_seconds",
                   "slowest_stage", "warnings", "statistics"}


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return path


def _bad_pdf(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")
    return path


def test_normal_mode_is_unchanged_and_has_no_diagnostics(tmp_path, capsys):
    path = _pdf(tmp_path)

    outcome = platform.analyze(str(path))
    assert main(["prerequisites", "analyze", str(path)]) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    api = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("p.pdf", path.read_bytes(), "application/pdf")}).json()

    assert "diagnostics" not in outcome and "diagnostics" not in api
    assert len(out) <= 4 and not any(line.startswith("Diagnostics") for line in out)


def test_diagnostic_mode_reports_the_run_in_the_json_result(tmp_path, capsys):
    assert main(["prerequisites", "analyze", str(_pdf(tmp_path)), "--json", "--diagnose"]) == EXIT_OK

    outcome = json.loads(capsys.readouterr().out)
    info = outcome["diagnostics"]
    assert set(info) == DIAGNOSTIC_KEYS and info["status"] == "success" and info["stage"] == "session_created"
    assert info["failed_after"] is None and info["warnings"] == [] and info["slowest_stage"] in info["stage_seconds"]
    assert info["completed_stages"][0] == "source_detector" and info["completed_stages"][-1] == "report_generator"
    assert info["stage_seconds"] == outcome["timings"] and info["statistics"] == outcome["report"]["statistics"]
    assert abs(info["total_seconds"] - sum(info["stage_seconds"].values())) < 1e-5


def test_diagnostic_mode_adds_a_concise_summary_to_the_human_output(tmp_path, capsys):
    assert main(["prerequisites", "analyze", str(_pdf(tmp_path)), "--diagnose"]) == EXIT_OK

    out = capsys.readouterr().out.splitlines()
    summary = [line for line in out if line.startswith("Diagnostics: success at stage session_created")]
    assert len(summary) == 1 and sum(1 for line in out if line.endswith("s") and line.startswith("  ") and ":" in line) >= 5
    assert any(line.startswith("  statistics: ") for line in out) and len(out) <= 14


def test_a_failed_run_reports_what_completed_and_where_it_stopped(tmp_path, capsys):
    bad = _bad_pdf(tmp_path)

    outcome = platform.analyze(str(bad), diagnostics=True)
    assert main(["prerequisites", "analyze", str(bad), "--diagnose"]) == EXIT_FAILURE
    err = capsys.readouterr().err

    info = outcome["diagnostics"]
    assert outcome["status"] == "failure" and set(info) == DIAGNOSTIC_KEYS and info["status"] == "failure"
    assert info["completed_stages"] == ["source_detector", "source_resolver"] and info["failed_after"] == "source_resolver"
    assert info["statistics"] is None and info["warnings"] == []
    assert "diagnostics: 2 stages completed; failed after source_resolver" in err and "Traceback" not in err


def test_diagnostics_hold_only_counts_and_timings_not_inputs_or_paths(tmp_path):
    path = _pdf(tmp_path)

    for outcome in (platform.analyze(str(path), diagnostics=True), platform.analyze(str(_bad_pdf(tmp_path)), diagnostics=True)):
        assert str(tmp_path) not in json.dumps(outcome["diagnostics"], default=str)


def test_the_failure_envelope_keeps_its_shape_without_diagnostics(tmp_path):
    outcome = platform.analyze(str(_bad_pdf(tmp_path)))

    assert set(outcome) == {"status", "stage", "detail", "error", "hint", "warnings"}
