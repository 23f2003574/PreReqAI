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
    assert maximum == 9 and difficulty_level(maximum) == "Expert"
    assert {difficulty_level(n) for n in range(maximum + 1)} == {"Beginner", "Intermediate", "Advanced", "Expert"}
