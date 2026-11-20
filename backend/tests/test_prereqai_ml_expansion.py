"""The fifty modern ML concepts: table integrity, alias resolution, rule graph, ambiguity gating, resources, quiz depth and end-to-end detection and planning."""
import re
from types import SimpleNamespace

import pytest

from backend.concepts.concept_explanation_engine import ConceptExplanationEngine
from backend.concepts.concept_registry import ConceptRegistry
from backend.concepts.ml_expansion import ALIAS_CONTEXT, AMBIGUOUS, EXPANSION
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph
from backend.platform import platform
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner
from backend.resources.learning_resource_recommender import LearningResourceRecommender
from backend.tutor.quiz_bank import QUIZ_BANK, QUIZ_EXPLANATIONS
from backend.tutor.rule_based_tutor import RuleBasedTutor

pytestmark = pytest.mark.prereqai

NAMES = [row[0] for row in EXPANSION]
REGISTRY = {c.name: c for c in ConceptRegistry().all()}
RULES = PrerequisiteDetector.PREREQUISITE_RULES


def detect(text):
    paper = Paper(source_path="x", metadata=None)
    paper.paragraphs = [Paragraph(1, "Method", text)]
    return {c.name: c.occurrences for c in RuleBasedConceptDetector().detect(paper).concepts}


def test_there_are_fifty_unique_concepts_and_no_alias_belongs_to_two():
    assert len(NAMES) == 50 == len(set(NAMES))
    terms = [t.lower() for c in ConceptRegistry().all() for t in (c.name, *c.aliases)]
    assert len(terms) == len(set(terms))


@pytest.mark.parametrize("name", NAMES)
def test_each_concept_is_wired_with_rules_resource_explanation_and_two_real_questions(name):
    assert name in REGISTRY and RULES[name] and all(t in PrerequisiteLearningPlanner.STUDY_ORDER for t in RULES[name])
    assert name not in RULES[name] and len(set(RULES[name])) == len(RULES[name])
    definition, level = ConceptExplanationEngine.EXPLANATIONS[name]
    assert len(definition) > 40 and level in {"Beginner", "Intermediate", "Advanced"}
    title, provider, url, hours = LearningResourceRecommender.for_concept(name)
    assert title and provider and url.startswith("http") and hours > 0
    questions = QUIZ_BANK[name]
    assert len(questions) >= 2 and len({q["question"] for q in questions}) == len(questions)
    for q in questions:
        assert q["question"].endswith("?") and len(q["answer"]) > 15 and len(QUIZ_EXPLANATIONS[(name, q["question"])]) > 15 and q["difficulty"] in {"Easy", "Medium", "Hard"}
        assert name.lower() not in q["answer"].lower() or len(q["answer"]) > 40  # no placeholder "X is X" answers


def test_the_rule_graph_is_acyclic_and_only_planner_subjects_are_targets():
    for name in NAMES:
        assert all(target not in RULES or target not in NAMES for target in RULES[name])  # new concepts never need each other, so no cycle is possible
    assert {t for n in NAMES for t in RULES[n]} <= set(PrerequisiteLearningPlanner.STUDY_ORDER)


def test_every_alias_is_detected_as_its_concept():
    for row in EXPANSION:
        for term in (row[0], *row[2]):
            if row[0] in AMBIGUOUS:
                continue
            guard = " Documents are split into passages for retrieval." if term in {t for guarded, _ in ALIAS_CONTEXT.get(row[0], ()) for t in guarded} else ""
            assert row[0] in detect(f"We build on {term} in a neural network trained with a softmax loss.{guard}"), term  # a guarded alias needs its context (see alias_context)


@pytest.mark.parametrize("text", [
    "We clip the gradient norm and watched a short video clip of the robot.",
    "Alignment of the two text columns improves readability, and a good alignment of teeth matters.",
    "The clip on the wall held the poster in place and the alignment was off.",
])
def test_everyday_uses_of_ambiguous_terms_do_not_count(text):
    assert not set(detect(text)) & set(AMBIGUOUS)


def test_clip_the_ratio_and_clip_the_gradient_do_not_detect_clip_models():
    found = detect("PPO uses a clipped objective: we clip the probability ratio, and we clip the gradient norm of the policy network.")
    assert "Contrastive Language-Image Pretraining" not in found and "Proximal Policy Optimization" in detect("Proximal Policy Optimization clips the ratio.")


def test_technical_uses_of_ambiguous_terms_count():
    assert "Contrastive Language-Image Pretraining" in detect("The CLIP model embeds the image and the caption with a contrastive objective.")
    assert "AI Alignment" in detect("AI alignment aims to make language models follow human feedback and preferences.")


def test_longer_names_keep_the_older_concepts_counts_clean():
    found = detect("We use a Masked Autoencoder. The Deep Deterministic Policy Gradient agent is an actor-critic method.")
    assert found.get("Masked Autoencoder") == 1 and "Autoencoder" not in found and found.get("Deep Deterministic Policy Gradient") == 1 and "Policy Gradient" not in found


PAPER = ("Method. We pretrain with SimCLR and an InfoNCE loss, then align the model with Direct Preference Optimization using a reward model. "
         "A Mixture of Experts layer with Expert Routing and a load balancing loss supports retrieval through a Vector Database searched by HNSW. " * 2)


def test_new_concepts_are_detected_planned_and_explained_end_to_end():
    found = detect(PAPER)
    wanted = {"SimCLR", "InfoNCE Loss", "Direct Preference Optimization", "Reward Model", "Mixture of Experts", "Expert Routing", "Load Balancing Loss", "Vector Database", "Hierarchical Navigable Small World"}
    assert wanted <= set(found)
    paper = PrerequisiteDetector().detect(_paper_with(found))
    subjects = {p.concept for p in paper.prerequisites}
    assert {"Information Theory", "Probability", "Optimization", "Graphs"} <= subjects  # InfoNCE, DPO, load balancing, HNSW


def _paper_with(found):
    paper = Paper(source_path="x", metadata=None)
    paper.paragraphs = [Paragraph(1, "Method", PAPER)]
    return RuleBasedConceptDetector().detect(paper)


def test_the_tutor_gives_the_curated_link_of_a_new_concept():
    paper = _paper_with(None)
    answer = RuleBasedTutor._resources_answer(paper, "Which resources can I use to learn Direct Preference Optimization?")
    assert "arxiv.org/abs/2305.18290" in answer


def test_revealing_any_question_returns_its_explanation():
    from backend.tutor import quiz_session

    session = SimpleNamespace(quiz_pending={}, quiz_attempts=[])
    for concept, expected in (("Direct Preference Optimization", True), ("Attention", True)):  # an older question has one too since every question was explained
        question = QUIZ_BANK[concept][0]
        identifier = quiz_session.question_id(concept, 1)
        session.quiz_pending[identifier] = {"revealed": False}
        revealed = quiz_session.reveal(session, identifier)
        assert revealed["answer"] == question["answer"] and ("explanation" in revealed) is expected
