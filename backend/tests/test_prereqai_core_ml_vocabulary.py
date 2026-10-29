"""Core vocabulary of the target paper domains (reinforcement learning, language models, losses, maximum likelihood) is detected
with prerequisites and definitions; before this a reinforcement-learning or language-model paper listed none of its own subject."""
import pytest

from backend.concepts.concept_explanation_engine import ConceptExplanationEngine
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai


def _detect(text, section="Body"):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title=section, content=text))
    RuleBasedConceptDetector().detect(paper)
    return paper, {concept.name: concept.occurrences for concept in paper.concepts}


def test_the_core_terms_are_detected_with_aliases_and_plurals():
    _, found = _detect(
        "Reinforcement learning agents are trained with cross-entropy and maximum likelihood (MLE). "
        "Large language models such as BERT and GPT-4 are LLMs.")
    assert found == {"Reinforcement Learning": 1, "Cross-Entropy Loss": 1, "Maximum Likelihood Estimation": 2, "Large Language Model": 4}


def test_everyday_words_and_bibliography_titles_are_not_concepts():
    assert _detect("The policy was to reward effort; learning in a reinforced wall; a language model of grammar.")[1] == {}
    assert _detect("Deep reinforcement learning, a survey.", section="References")[1] == {}


def test_each_has_prerequisites_that_exist_and_a_definition():
    paper, found = _detect("Reinforcement learning, large language models, cross-entropy and maximum likelihood.")
    assert len(found) == 4
    PrerequisiteDetector().detect(paper)
    assert {"Probability", "Calculus", "Neural Networks", "Linear Algebra", "Information Theory"} <= {item.concept for item in paper.prerequisites}
    ConceptExplanationEngine().explain(paper)
    assert {item.concept for item in paper.concept_explanations} == set(found)
