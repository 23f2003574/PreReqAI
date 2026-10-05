"""Final-state integrity of the PreReqAI analysis workflow: every result is one of
five terminal states, success is only possible after every stage completed and
with a complete output of its own, and anything else is never reported as one."""
import fitz
import pytest
import requests

import backend.ingestion.arxiv_resolver as arxiv_resolver
from backend.api.workflow_result import TERMINAL_STATUSES, terminal_violations
from backend.pipeline.research_paper_pipeline import PIPELINE_STAGES, PipelineResult, ResearchPaperPipeline
from backend.platform import AnalysisLimits, PreReqAIPlatform
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


def test_the_stage_list_that_defines_completeness_is_what_the_pipeline_really_runs(tmp_path):
    assert tuple(ResearchPaperPipeline().run(_pdf(tmp_path)).timings) == PIPELINE_STAGES


def test_successful_completion_is_a_valid_success_with_every_stage_done(platform, tmp_path):
    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True)

    assert outcome["status"] == "success" and terminal_violations(outcome) == []
    assert tuple(outcome["timings"]) == PIPELINE_STAGES and outcome["diagnostics"]["failed_after"] is None


def test_every_non_success_terminal_state_is_valid_distinct_and_carries_no_output(platform, tmp_path, monkeypatch):
    paper = _pdf(tmp_path)
    monkeypatch.setattr(arxiv_resolver.requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.ReadTimeout("slow")))
    resolver = platform.analysis.source_resolver._resolvers["arxiv"]
    monkeypatch.setattr(resolver, "CACHE_DIRECTORY", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    sessions = len(session_manager.sessions)

    outcomes = {
        "failure": platform.analyze(str(tmp_path / "missing.pdf")),
        "cancelled": platform.analyze(paper, should_cancel=lambda: True),
        "timeout": platform.analyze("https://arxiv.org/abs/9999.54321"),
        "limit_exceeded": platform.analyze(paper, limits=AnalysisLimits(max_file_bytes=10)),
    }

    for expected, outcome in outcomes.items():
        assert outcome["status"] == expected and terminal_violations(outcome) == [], expected
        assert not {"session_id", "report", "timings"} & set(outcome)
    assert len(session_manager.sessions) == sessions and set(TERMINAL_STATUSES) == {"success", *outcomes}


@pytest.mark.parametrize("break_it", ["drop_stages", "drop_report_keys"])
def test_a_partial_result_is_a_finalization_failure_and_never_opens_a_session(platform, tmp_path, monkeypatch, break_it):
    real = platform.analysis.run

    def partial(path, should_cancel=None):
        result = real(path, should_cancel=should_cancel)
        if break_it == "drop_stages":
            return PipelineResult(paper=result.paper, report=result.report, timings=dict(list(result.timings.items())[:10]))
        return PipelineResult(paper=result.paper, report={"paper": result.report["paper"]}, timings=result.timings)

    monkeypatch.setattr(platform.analysis, "run", partial)
    sessions = len(session_manager.sessions)

    outcome = platform.analyze(_pdf(tmp_path))

    assert outcome["status"] == "failure" and outcome["stage"] == "finalization" and "did not complete" in outcome["detail"]
    assert "session_id" not in outcome and "report" not in outcome and len(session_manager.sessions) == sessions


def test_an_invalid_terminal_result_from_anywhere_is_replaced_by_a_finalization_failure(platform, monkeypatch):
    bad_results = [
        {"status": "weird", "warnings": []},
        {"status": "success", "stage": "session_created", "warnings": []},  # success with no output
        {"status": "cancelled", "stage": "analysis", "error": None, "warnings": [], "report": {}},  # output on a non-success
        {"status": "success", "stage": "session_created", "warnings": [], "session_id": "x", "report": {}, "timings": {}},
    ]
    for bad in bad_results:
        monkeypatch.setattr(platform, "_analyze", lambda *a, _bad=bad, **k: _bad)

        outcome = platform.analyze("ignored.pdf")

        assert outcome["status"] == "failure" and outcome["stage"] == "finalization" and terminal_violations(outcome) == []


def test_warnings_do_not_turn_a_success_into_a_failure(platform, tmp_path):
    outcome = platform.analyze(_pdf(tmp_path))
    with_warning = {**outcome, "warnings": ["a warning that is not an error"]}

    assert terminal_violations(with_warning) == [] and with_warning["status"] == "success"
    assert terminal_violations({**outcome, "warnings": "oops"}) == ["warnings must be a list"]


def test_the_result_references_only_state_belonging_to_this_invocation(platform, tmp_path):
    paper = _pdf(tmp_path)

    first, second = platform.analyze(paper), platform.analyze(paper)

    for outcome in (first, second):  # the session holds an equal report of its own, not the caller's object
        stored = session_manager.get(outcome["session_id"]).report
        assert stored == outcome["report"] and stored is not outcome["report"]
    assert first["session_id"] != second["session_id"] and first["report"] is not second["report"]
    assert first["timings"] is not second["timings"]
