"""Per-stage wall-clock timings of the PreReqAI analysis pipeline: recorded for
each major stage, reported in the workflow result and (concisely) by the CLI,
and without changing what the workflow returns."""
import json

import pymupdf as fitz
from fastapi.testclient import TestClient

from backend.cli import EXIT_OK, main
from backend.main import app
from backend.pipeline.research_paper_pipeline import PipelineResult, ResearchPaperPipeline
from backend.platform import platform

MAJOR_STAGES = {
    "source_detector", "source_resolver", "ingestion", "section_parser", "table_extractor", "concept_detector",
    "prerequisite_detector", "learning_planner", "readiness_engine", "graph_builder", "report_generator",
}


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return path


def test_every_major_stage_is_timed_in_order_with_non_negative_durations(tmp_path):
    result = ResearchPaperPipeline().run(str(_pdf(tmp_path)))

    assert MAJOR_STAGES <= set(result.timings)
    assert list(result.timings)[:3] == ["source_detector", "source_resolver", "ingestion"]  # recorded in pipeline order
    assert list(result.timings)[-1] == "report_generator"
    assert all(isinstance(v, float) and v >= 0 for v in result.timings.values())


def test_timing_does_not_change_the_workflow_result(tmp_path):
    path = str(_pdf(tmp_path))

    first, second = ResearchPaperPipeline().run(path), ResearchPaperPipeline().run(path)

    assert first.report == second.report  # same report on every run, timings aside
    assert PipelineResult(paper=first.paper, report=first.report).timings == {}  # existing callers need not pass timings


def test_the_workflow_result_and_the_api_include_the_timings(tmp_path):
    outcome = platform.analyze(str(_pdf(tmp_path)))
    api = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("p.pdf", _pdf(tmp_path).read_bytes(), "application/pdf")})

    assert outcome["status"] == "success" and MAJOR_STAGES <= set(outcome["timings"])
    assert api.status_code == 200 and MAJOR_STAGES <= set(api.json()["timings"])


def test_failures_do_not_carry_timings_and_keep_their_shape(tmp_path):
    outcome = platform.analyze(str(tmp_path / "missing.pdf"))

    assert outcome["status"] == "failure" and "timings" not in outcome


def test_the_cli_adds_one_concise_time_line_and_json_has_the_full_timings(tmp_path, capsys):
    path = _pdf(tmp_path)

    assert main(["prerequisites", "analyze", str(path)]) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    time_lines = [line for line in out if line.startswith("  time: ")]
    assert len(time_lines) == 1 and "slowest stage:" in time_lines[0] and len(out) <= 5

    assert main(["prerequisites", "analyze", str(path), "--json"]) == EXIT_OK
    assert MAJOR_STAGES <= set(json.loads(capsys.readouterr().out)["timings"])
