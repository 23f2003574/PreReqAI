import pytest

from backend.study_plan_markdown import studied_concepts

pytestmark = pytest.mark.prereqai


def test_studied_concepts_lists_only_completed_items_and_tolerates_a_missing_section():
    report = {"study_progress": [
        {"concept": "Probability", "completed": True},
        {"concept": "Calculus", "completed": False},
        {"concept": "Linear Algebra"},
    ]}
    assert studied_concepts(report) == {"Probability"}
    assert studied_concepts({}) == set()
