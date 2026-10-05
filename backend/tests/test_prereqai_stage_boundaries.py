"""Stage boundaries of the analysis workflow: stages run in their declared
order, each gets the output of the stages before it, and a stage that fails
stops the run with neither it nor any later stage reported as completed."""
import fitz
import pytest

from backend.pipeline.research_paper_pipeline import _STAGES, PIPELINE_STAGES
from backend.platform import PreReqAIPlatform


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


@pytest.fixture
def platform():
    return PreReqAIPlatform()


def test_every_stage_reads_only_what_the_caller_or_an_earlier_stage_produced():
    available = {"file_path"}
    for stage, _, _, inputs, output in _STAGES:
        assert set(inputs) <= available, stage
        available.add(output)
    assert {"paper", "report"} <= available


def test_stages_complete_in_their_declared_order(platform, tmp_path):
    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True)

    assert outcome["status"] == "success"
    assert outcome["diagnostics"]["completed_stages"] == list(PIPELINE_STAGES)
    assert outcome["diagnostics"]["failed_stage"] is None


def test_an_intermediate_stage_failure_stops_the_run_and_later_stages_are_not_completed(platform, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(platform.analysis.missing_prerequisite_analyzer, "analyze", lambda paper: (_ for _ in ()).throw(ValueError("broken")))
    monkeypatch.setattr(platform.analysis.learning_planner, "generate", lambda paper: calls.append(paper) or paper)

    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True)

    failed = PIPELINE_STAGES.index("missing_prerequisite_analyzer")
    info = outcome["diagnostics"]
    assert outcome["status"] == "failure" and outcome["stage"] == "analysis" and outcome["error"]["type"] == "ValueError"
    assert info["failed_stage"] == "missing_prerequisite_analyzer" and info["failed_after"] == PIPELINE_STAGES[failed - 1]
    assert info["completed_stages"] == list(PIPELINE_STAGES[:failed])  # not the failed stage, nothing after it
    assert calls == [] and "report" not in outcome and "session_id" not in outcome


def test_an_unreadable_paper_fails_at_ingestion_with_only_earlier_stages_completed(platform, tmp_path):
    outcome = platform.analyze(str(tmp_path / "missing.pdf"), diagnostics=True)

    info = outcome["diagnostics"]
    assert outcome["status"] == "failure" and info["failed_stage"] == "ingestion"
    assert info["completed_stages"] == ["source_detector", "source_resolver"] and info["failed_after"] == "source_resolver"
