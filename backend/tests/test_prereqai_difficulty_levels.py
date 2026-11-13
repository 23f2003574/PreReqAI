import pytest

from backend.prerequisites.difficulty_assessment_engine import difficulty_level
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector


@pytest.mark.parametrize("missing, level", [
    (0, "Beginner"), (2, "Beginner"), (3, "Intermediate"), (4, "Intermediate"),
    (5, "Advanced"), (6, "Advanced"), (7, "Expert"), (8, "Expert"),
])
def test_every_boundary_maps_to_one_level(missing, level):
    assert difficulty_level(missing) == level


def test_the_most_a_paper_can_miss_is_expert_and_all_levels_are_reachable():
    maximum = len({p for rule in PrerequisiteDetector.PREREQUISITE_RULES.values() for p in rule})
    assert maximum == 12 and difficulty_level(maximum) == "Expert"
    assert {difficulty_level(n) for n in range(maximum + 1)} == {"Beginner", "Intermediate", "Advanced", "Expert"}


# --- effort-based level: the level follows the hours of the missing subjects, not just how many there are ---
from types import SimpleNamespace as N

from backend.prerequisites.difficulty_assessment_engine import (
    LEVEL_BANDS,
    HOUR_BANDS, HOURS_PER_SUBJECT, DifficultyAssessmentEngine, describe_contributors, level_for_hours, prerequisite_effort)
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner


def paper_missing(*names, essential=()):
    return N(concepts=[N(name="X")], prerequisites=[N(concept=n, importance="essential" if n in essential else "supporting") for n in names],
             missing_prerequisites=[N(concept=n, satisfied=False) for n in names])


def test_two_missing_subjects_with_different_effort_get_different_levels():
    heavy = DifficultyAssessmentEngine().assess(paper_missing("Neural Networks", "Linear Algebra")).difficulty   # 27 h
    light = DifficultyAssessmentEngine().assess(paper_missing("Graphs", "Information Theory")).difficulty       # 16 h
    assert (light.level, heavy.level) == ("Beginner", "Intermediate") and light.score < heavy.score


def test_the_level_never_drops_as_study_hours_grow_and_bands_match_the_count_bands():
    levels = [level_for_hours(h / 2) for h in range(0, 400)]
    order = [lvl for lvl, _ in LEVEL_BANDS] + ["Expert"]
    assert [order.index(x) for x in levels] == sorted(order.index(x) for x in levels) and set(levels) == set(order)
    for (level, upper), (_, hours) in zip(LEVEL_BANDS, HOUR_BANDS):
        assert level_for_hours(hours) == level and level_for_hours(hours + 0.01) != level and hours == upper * HOURS_PER_SUBJECT


def test_a_paper_missing_an_average_subject_count_keeps_its_old_level():
    assert level_for_hours(0) == "Beginner" and level_for_hours(2 * HOURS_PER_SUBJECT) == "Beginner"
    assert level_for_hours(4 * HOURS_PER_SUBJECT) == "Intermediate" and level_for_hours(6 * HOURS_PER_SUBJECT) == "Advanced"


def test_explanation_names_the_biggest_contributors_deterministically():
    paper = paper_missing("Graphs", "Neural Networks", "Linear Algebra", "Calculus", essential=("Linear Algebra", "Graphs"))
    first = DifficultyAssessmentEngine().assess(paper).difficulty.explanation
    assert first == DifficultyAssessmentEngine().assess(paper).difficulty.explanation
    assert first.startswith("4 prerequisite concepts require additional study, about 45 hours")
    assert "Linear Algebra (12h, essential), Graphs (8h, essential), Neural Networks (15h, supporting) and 1 more" in first


def test_a_missing_hour_estimate_counts_at_the_fallback_and_is_flagged(monkeypatch):
    paper = paper_missing("Topology")
    entry, = prerequisite_effort(paper)
    assert entry[1] == PrerequisiteLearningPlanner.FALLBACK_HOURS and entry[3] is False and "estimated" in describe_contributors([entry])
    monkeypatch.setitem(PrerequisiteLearningPlanner.STUDY_TIME, "Graphs", float("nan"))
    assert prerequisite_effort(paper_missing("Graphs"))[0][1] == PrerequisiteLearningPlanner.FALLBACK_HOURS


def test_satisfied_and_repeated_prerequisites_add_no_effort():
    paper = paper_missing("Calculus", "Calculus")
    paper.missing_prerequisites.append(N(concept="Probability", satisfied=True))
    assert [e[0] for e in prerequisite_effort(paper)] == ["Calculus"]
