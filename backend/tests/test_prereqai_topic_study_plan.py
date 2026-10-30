"""A question's topic may name a study-plan prerequisite (Probability), not only a concept the paper names."""
import pytest

from backend.api.session_routes import resolve_topic
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _session():
    return session_manager.get(platform.analyze(SAMPLE)["session_id"])


def test_a_study_plan_prerequisite_is_a_valid_topic_case_insensitively_and_paper_concepts_still_are():
    session = _session()
    assert resolve_topic(session, "probability") == ("Probability", None)
    assert resolve_topic(session, " Linear Algebra ") == ("Linear Algebra", None)
    assert resolve_topic(session, "softmax") == ("Softmax", None)


def test_a_topic_in_neither_the_paper_nor_the_study_plan_is_still_rejected_and_the_hint_lists_the_plan():
    topic, hint = resolve_topic(_session(), "Cooking")
    assert topic is None and "Probability" in hint and "Softmax" in hint


def test_a_topic_marked_known_leaves_the_plan_and_is_rejected():
    session = _session()
    platform.mark_concept_known(session.session_id, "Calculus")
    assert resolve_topic(session_manager.get(session.session_id), "Calculus")[0] is None
