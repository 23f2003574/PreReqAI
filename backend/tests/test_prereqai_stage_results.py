"""Stage results at the orchestration boundary: a stage's own payload is kept,
a stage returning the wrong shape fails at that stage (never feeding later
stages), and every way a run stops maps to one distinct terminal status."""
import pymupdf as fitz
import pytest
import requests

from backend.api.workflow_result import success_body, terminal_violations
from backend.pipeline.research_paper_pipeline import PIPELINE_STAGES, PipelineCancelled
from backend.platform import AnalysisLimits, PreReqAIPlatform
from backend.platform.prereqai_platform import _stopped_outcome
from backend.session import session_manager


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


@pytest.fixture
def platform():
    return PreReqAIPlatform()


def test_a_successful_stage_payload_reaches_the_report_unchanged(platform, tmp_path, monkeypatch):
    real = platform.analysis.concept_detector.detect
    seen = {}
    monkeypatch.setattr(platform.analysis.concept_detector, "detect", lambda paper: seen.setdefault("paper", real(paper)))

    outcome = platform.analyze(_pdf(tmp_path))

    assert outcome["status"] == "success" and terminal_violations(outcome) == []
    assert [c.name for c in seen["paper"].concepts] == list(outcome["report"]["concepts"])


def test_warnings_ride_on_a_success_without_changing_its_status():
    outcome = success_body("Prerequisite Explorer", "session_created", warnings=["few concepts"],
                           session_id="s", report={key: {} for key in ("paper", "concepts", "prerequisites", "missing_prerequisites",
                                                                    "learning_plan", "readiness", "statistics")}, timings={})

    assert outcome["status"] == "success" and outcome["warnings"] == ["few concepts"] and terminal_violations(outcome) == []


def test_a_stage_returning_nothing_fails_there_and_feeds_no_later_stage(platform, tmp_path, monkeypatch):
    later = []
    monkeypatch.setattr(platform.analysis.prerequisite_detector, "detect", lambda paper: None)  # a missing `return paper`
    monkeypatch.setattr(platform.analysis.justification_engine, "justify", lambda paper: later.append(paper) or paper)
    sessions = len(session_manager.sessions)

    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True)

    failed = PIPELINE_STAGES.index("prerequisite_detector")
    assert outcome["status"] == "failure" and outcome["error"]["type"] == "TypeError"
    assert "prerequisite_detector returned NoneType" in outcome["detail"]
    assert outcome["diagnostics"]["failed_stage"] == "prerequisite_detector"
    assert outcome["diagnostics"]["completed_stages"] == list(PIPELINE_STAGES[:failed])
    assert later == [] and "report" not in outcome and len(session_manager.sessions) == sessions


@pytest.mark.parametrize("exc, limits, status", [
    (PipelineCancelled("stop"), None, "cancelled"),
    (PipelineCancelled("stop"), AnalysisLimits(max_seconds=1), "limit_exceeded"),
    (requests.exceptions.ReadTimeout("slow"), None, "timeout"),
    (TimeoutError("slow"), None, "timeout"),
    (ValueError("bad pdf"), None, "failure"),
])
def test_every_way_a_run_stops_is_a_distinct_valid_terminal_status(exc, limits, status):
    outcome = _stopped_outcome(exc, limits)

    assert outcome["status"] == status and outcome["stage"] == "analysis" and terminal_violations(outcome) == []
