"""The study plan and the resource list quote the same hours for a concept (the planner's STUDY_TIME is the one source)."""
import pytest

from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner as Planner
from backend.resources.learning_resource_recommender import LearningResourceRecommender as Recommender

pytestmark = pytest.mark.prereqai


def test_every_resource_has_the_planner_hours():
    assert {c: r[3] for c, r in Recommender.RESOURCE_LIBRARY.items()} == {c: Planner.STUDY_TIME[c] for c in Recommender.RESOURCE_LIBRARY}


def test_no_resource_concept_is_missing_from_the_planner():
    assert set(Recommender.RESOURCE_LIBRARY) <= set(Planner.STUDY_TIME)


@pytest.mark.parametrize("concept,hours", [("Graphs", 8), ("Attention", 8), ("Markov Decision Process", 8), ("Transformer", 10)])
def test_previously_inconsistent_subjects_agree(concept, hours):
    assert Recommender.RESOURCE_LIBRARY[concept][3] == Planner.STUDY_TIME[concept] == hours
