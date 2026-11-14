"""The concepts added to the registry are detected, explained, ruled, graphed and (where supported) quizzed; aliases do not over-match."""
import pytest

from backend.concepts.concept_explanation_engine import ConceptExplanationEngine
from backend.concepts.concept_registry import ConceptRegistry
from backend.graph.concept_relationship_builder import ConceptRelationshipBuilder
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.tutor.quiz_bank import QUIZ_BANK

pytestmark = pytest.mark.prereqai

ADDED = ["Parameter-Efficient Fine-Tuning", "LoRA", "Reinforcement Learning from Human Feedback", "Proximal Policy Optimization",
         "Contrastive Learning", "Tokenization", "Vision Transformer"]
NAMES = {c.name for c in ConceptRegistry().all()}


@pytest.mark.parametrize("name", ADDED)
def test_each_added_concept_is_wired_through_the_pipeline_tables(name):
    assert name in NAMES
    assert PrerequisiteDetector.PREREQUISITE_RULES.get(name)
    assert name in ConceptExplanationEngine.EXPLANATIONS


def test_registry_has_no_duplicate_names_or_aliases():
    terms = [t.lower() for c in ConceptRegistry().all() for t in (c.name, *c.aliases)]
    assert len(terms) == len(set(terms))


def test_relationships_only_join_registry_concepts():
    for source, targets in ConceptRelationshipBuilder.RELATIONSHIPS.items():
        assert {source, *targets} <= NAMES


def test_quiz_entries_are_for_registry_concepts():
    assert set(QUIZ_BANK) <= NAMES and {"LoRA", "Proximal Policy Optimization", "Tokenization", "Vision Transformer"} <= set(QUIZ_BANK)


def _detect(text):
    import types
    from backend.concepts import RuleBasedConceptDetector
    from backend.models import Paper, Paragraph
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs = [Paragraph(paragraph_id=1, section_title="Method", content=text)]
    return {c.name: c.occurrences for c in RuleBasedConceptDetector().detect(paper).concepts}


def test_aliases_detect_the_added_concepts():
    found = _detect("We apply LoRA (low-rank adaptation) with PPO for RLHF, a ViT, BPE tokenization and InfoNCE contrastive learning.")
    assert set(ADDED) - {"Parameter-Efficient Fine-Tuning"} <= set(found)


def test_longer_concepts_do_not_also_count_their_parts():
    found = _detect("The Vision Transformer splits an image. PEFT such as LoRA avoids full fine-tuning.")
    assert "Transformer" not in found and found["Vision Transformer"] == 1
    assert found["Parameter-Efficient Fine-Tuning"] == 1 and "Fine-Tuning" in found  # the standalone 'fine-tuning' still counts


def test_ordinary_words_are_not_detected():
    assert not set(_detect("A token of appreciation; the vision of a contrast; policy optimization of proximal gains.")) & set(ADDED)


CLASSICAL = ["Principal Component Analysis", "Support Vector Machine", "K-Means Clustering", "Decision Tree", "Random Forest",
             "Logistic Regression", "Regularization", "Cross-Validation"]


@pytest.mark.parametrize("name", CLASSICAL)
def test_each_classical_ml_concept_has_rules_on_known_subjects_an_explanation_and_a_quiz(name):
    from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner as Planner
    from backend.resources.learning_resource_recommender import LearningResourceRecommender  # noqa: F401
    assert name in NAMES and name in ConceptExplanationEngine.EXPLANATIONS and name in QUIZ_BANK
    needs = PrerequisiteDetector.PREREQUISITE_RULES[name]
    assert needs and all(subject in Planner.STUDY_TIME and subject in Planner.STUDY_ORDER for subject in needs)


def test_classical_ml_terms_are_detected_in_a_representative_paper():
    found = _detect("We reduce dimension with PCA, then train an SVM and k-means baseline. A random forest and a decision tree use "
                    "L2 regularisation chosen by k-fold cross-validation; logistic regression is the linear baseline.")
    assert set(CLASSICAL) <= set(found)


def test_classical_ml_names_do_not_match_ordinary_words():
    assert not set(_detect("The principal component of the plan was a support group; a tree of decisions in a forest, "
                           "a regular logistics model, and a validation of crosses.")) & set(CLASSICAL)
