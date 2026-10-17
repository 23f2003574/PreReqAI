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
    assert done == {"Probability"} and len(generations) == 2


def test_unmatched_studied_name_does_not_rebuild_the_report(generations):
    outcome = platform.analyze(SAMPLE, studied=["Not A Concept"])
    assert len(generations) == 1 and any("Not A Concept" in w for w in outcome["warnings"])
