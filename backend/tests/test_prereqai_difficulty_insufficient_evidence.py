"""A paper with no detected concepts is "Unknown" difficulty, never "Beginner"; assessable papers keep the four levels."""
import pytest

from backend.models import DetectedConcept, MissingPrerequisite, Paper
from backend.prerequisites import DifficultyAssessmentEngine, DifficultyExplanationEngine
from backend.prerequisites.difficulty_assessment_engine import UNKNOWN_LEVEL, difficulty_level

pytestmark = pytest.mark.prereqai


# Real subjects in this order add 8, 8, 8, 8, 10, 10, 10, 12 and 15 curated hours, so n missing subjects total about n average subjects.
SUBJECTS = ["Graphs", "Information Theory", "Markov Decision Process", "Attention", "Probability", "Calculus", "Transformer",
            "Linear Algebra", "Neural Networks"]


def _paper(concepts=0, missing=0, satisfied=0):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.concepts = [DetectedConcept(name=f"K{i}", domain="d", occurrences=3) for i in range(concepts)]
    paper.missing_prerequisites = [MissingPrerequisite(concept=SUBJECTS[i], satisfied=False, reason="r") for i in range(missing)]
    paper.missing_prerequisites += [MissingPrerequisite(concept=f"S{i}", satisfied=True, reason="r") for i in range(satisfied)]
    return paper


def test_zero_concepts_is_unknown_not_beginner():
    paper = DifficultyAssessmentEngine().assess(_paper())
    assert paper.difficulty.level == UNKNOWN_LEVEL == "Unknown" and paper.difficulty.score == 0.0
    assert "Not enough evidence" in paper.difficulty.explanation and "easy" not in paper.difficulty.explanation


def test_zero_concepts_explanation_says_insufficient_evidence():
    paper = DifficultyExplanationEngine().explain(_paper())
    assert [e.title for e in paper.difficulty_explanations] == ["Insufficient Evidence"]


def test_a_single_concept_with_nothing_missing_is_a_real_beginner_rating():
    paper = DifficultyAssessmentEngine().assess(_paper(concepts=1, satisfied=1))
    assert paper.difficulty.level == "Beginner" and paper.difficulty.score == 1.0
    assert not any(e.title == "Insufficient Evidence" for e in DifficultyExplanationEngine().explain(_paper(concepts=1)).difficulty_explanations)


@pytest.mark.parametrize("missing, level", [(0, "Beginner"), (2, "Beginner"), (3, "Intermediate"), (4, "Intermediate"),
                                             (5, "Advanced"), (6, "Advanced"), (7, "Expert"), (8, "Expert")])
def test_assessable_papers_keep_the_four_levels(missing, level):
    paper = DifficultyAssessmentEngine().assess(_paper(concepts=5, missing=missing))
    assert paper.difficulty.level == level == difficulty_level(missing)
    assert f"{missing} prerequisite concepts" in paper.difficulty.explanation
