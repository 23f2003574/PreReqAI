"""The report is rebuilt only as often as the progress actually changed."""
import pytest

from backend.platform import platform
from backend.reporting.learning_report_generator import LearningReportGenerator

SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture
def generations(monkeypatch):
    calls = []
    original = LearningReportGenerator.generate
    monkeypatch.setattr(LearningReportGenerator, "generate", lambda self, paper: calls.append(1) or original(self, paper))
    return calls


def test_marking_known_without_studied_concepts_builds_the_report_once(generations):
    sid = platform.analyze(SAMPLE)["session_id"]
    generations.clear()
    platform.mark_concept_known(sid, "Calculus")
    assert len(generations) == 1


def test_marking_known_with_a_studied_concept_still_restores_its_progress(generations):
    sid = platform.analyze(SAMPLE)["session_id"]
    platform.mark_concept_studied(sid, "Probability")
    generations.clear()
    report = platform.mark_concept_known(sid, "Calculus")
    done = {item["concept"] for item in report["study_progress"] if item["completed"]}
    assert done == {"Probability"} and len(generations) == 1  # studied progress is restored inside the one rebuild


def test_unmatched_studied_name_does_not_rebuild_the_report(generations):
    outcome = platform.analyze(SAMPLE, studied=["Not A Concept"])
    assert len(generations) == 1 and any("Not A Concept" in w for w in outcome["warnings"])


def test_known_and_studied_together_rebuild_the_report_once_and_match_the_two_step_result(generations):
    both = platform.analyze(SAMPLE, known=["Calculus"], studied=["Probability", "Not A Concept"])
    assert len(generations) == 2  # the pipeline's own report plus the one personalised rebuild (it was three)
    assert any("'Not A Concept' is not in this paper's study plan" in w for w in both["warnings"])

    sid = platform.analyze(SAMPLE, known=["Calculus"])["session_id"]
    platform.mark_concept_studied(sid, "Probability")
    from backend.session import session_manager

    step_by_step = session_manager.get(sid).report
    for key in ("learning_plan", "study_time", "study_progress", "readiness", "prerequisite_tree", "study_actions", "study_roadmap"):
        assert both["report"][key] == step_by_step[key], key
