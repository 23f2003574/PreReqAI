"""A PreReqAI analysis run belongs only to its own invocation: after a
successful, failed or cancelled run, the next run on the same platform returns
exactly what a brand-new platform would, and no pipeline component keeps
per-run state."""
import json

import pymupdf as fitz
import pytest

from backend.platform import PreReqAIPlatform
from backend.session import session_manager


def _pdf(tmp_path, name, body):
    document = fitz.open()
    document.new_page().insert_text((72, 72), f"Paper {name}\n\nAbstract\n{body}\n\n1 Introduction\n{body}\n", fontsize=11)
    path = tmp_path / f"{name}.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _report(outcome):
    return json.dumps(outcome["report"], sort_keys=True, default=str)


def _component_state(platform):
    """Sizes/values of the plain attributes of every analysis-pipeline component."""
    state = {}
    for name, component in vars(platform.analysis).items():
        try:
            attributes = vars(component)
        except TypeError:
            continue
        for key, value in attributes.items():
            if isinstance(value, (list, dict, set, tuple)):
                state[f"{name}.{key}"] = len(value)
            elif isinstance(value, (int, float, str, bool)) or value is None:
                state[f"{name}.{key}"] = value
    return state


@pytest.fixture
def papers(tmp_path):
    return (
        _pdf(tmp_path, "A", "We use softmax and attention and convolution and backpropagation."),
        _pdf(tmp_path, "B", "We use gradient descent and the Fourier transform."),
    )


def test_the_two_test_papers_really_produce_different_reports(papers):
    platform = PreReqAIPlatform()

    assert _report(platform.analyze(papers[0])) != _report(platform.analyze(papers[1]))  # so the checks below are not vacuous


def test_a_successful_run_does_not_affect_the_next_run(papers):
    fresh = _report(PreReqAIPlatform().analyze(papers[1]))
    platform = PreReqAIPlatform()

    first = platform.analyze(papers[0])
    second = platform.analyze(papers[1])

    assert _report(second) == fresh and _report(second) != _report(first)
    assert first["session_id"] != second["session_id"]
    assert session_manager.get(second["session_id"]).report == second["report"]  # the session holds its own run's report


def test_a_cancelled_run_leaves_nothing_behind_for_the_next_run(papers):
    fresh = _report(PreReqAIPlatform().analyze(papers[1]))
    platform = PreReqAIPlatform()
    sessions = len(session_manager.sessions)
    polls = {"n": 0}

    def cancel_midway():
        polls["n"] += 1
        return polls["n"] > 10

    cancelled = platform.analyze(papers[0], should_cancel=cancel_midway)
    assert cancelled["status"] == "cancelled" and len(session_manager.sessions) == sessions

    next_run = platform.analyze(papers[1])
    assert next_run["status"] == "success" and _report(next_run) == fresh


def test_a_failed_run_leaves_nothing_behind_for_the_next_run(tmp_path, papers):
    fresh = _report(PreReqAIPlatform().analyze(papers[1]))
    platform = PreReqAIPlatform()
    sessions = len(session_manager.sessions)

    failed = platform.analyze(str(tmp_path / "missing.pdf"))
    assert failed["status"] == "failure" and len(session_manager.sessions) == sessions

    assert _report(platform.analyze(papers[1])) == fresh


def test_no_pipeline_component_accumulates_state_across_runs_of_any_outcome(tmp_path, papers):
    platform = PreReqAIPlatform()
    before = _component_state(platform)

    platform.analyze(papers[0])
    platform.analyze(str(tmp_path / "missing.pdf"))
    platform.analyze(papers[0], should_cancel=lambda: True)
    platform.analyze(papers[1])

    assert _component_state(platform) == before


def test_each_result_and_its_timings_belong_to_the_current_invocation(papers):
    platform = PreReqAIPlatform()

    first = platform.analyze(papers[0])
    second = platform.analyze(papers[0])

    assert first["timings"] is not second["timings"] and first["report"] is not second["report"]
    assert list(first["timings"]) == list(second["timings"])  # per-run stage list, not cumulative across runs
    assert _report(first) == _report(second) and first["session_id"] != second["session_id"]


def test_an_exception_carries_only_its_own_runs_stage_timings(tmp_path, papers):
    platform = PreReqAIPlatform()
    platform.analyze(papers[0])  # a completed run first

    outcome = platform.analyze(str(tmp_path / "missing.pdf"), diagnostics=True)

    assert outcome["diagnostics"]["completed_stages"] == ["source_detector", "source_resolver"]  # not the earlier run's stages
