import pytest

from backend.api.session_routes import resolve_topic
from backend.models import DetectedConcept, Paper, StudyProgress


def _session(concepts=("Gradient Descent", "Self-Attention"), plan=("Linear Algebra", "Neural Networks")):
    paper = Paper(source_path="p.pdf", metadata=None, pages=[], sections=[])
    paper.concepts = [DetectedConcept(name=name, domain="d", occurrences=1) for name in concepts]
    paper.study_progress = [StudyProgress(concept=name, completed=False, progress_percent=0) for name in plan]
    return type("Session", (), {"paper": paper})()


@pytest.mark.parametrize("spelling, expected", [
    ("gradient descent", "Gradient Descent"), ("GRADIENT-DESCENT", "Gradient Descent"), ("gradient  descent", "Gradient Descent"),
    ("Gradient_Descent", "Gradient Descent"), ("  gradient descent ", "Gradient Descent"), ("self attention", "Self-Attention"),
    ("linear-algebra", "Linear Algebra"), ("neural_networks", "Neural Networks"), ("Linear Algebra", "Linear Algebra"),
])
def test_equivalent_spellings_resolve_to_the_one_concept(spelling, expected):
    assert resolve_topic(_session(), spelling) == (expected, None)


@pytest.mark.parametrize("topic", ["gradient", "descent gradient", "Self", "Linear", "Quantum Gravity"])
def test_distinct_names_are_not_merged(topic):
    name, hint = resolve_topic(_session(), topic)
    assert name is None and "Gradient Descent" in hint


def test_no_topic_and_blank_topic_behave_as_before():
    assert resolve_topic(_session(), None) == (None, None)
    assert resolve_topic(_session(), "  ")[0] is None
