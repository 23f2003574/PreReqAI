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


REPRESENTATION = ["Knowledge Distillation", "Retrieval-Augmented Generation", "Beam Search", "Autoencoder", "Self-Supervised Learning", "Transfer Learning"]
ALIASES = {"model distillation": "Knowledge Distillation", "teacher-student distillation": "Knowledge Distillation", "distilling knowledge": "Knowledge Distillation",
           "RAG": "Retrieval-Augmented Generation", "retrieval augmented generation": "Retrieval-Augmented Generation", "beam decoding": "Beam Search",
           "auto-encoder": "Autoencoder", "denoising autoencoder": "Autoencoder", "sparse autoencoder": "Autoencoder",
           "self supervised learning": "Self-Supervised Learning", "self-supervised": "Self-Supervised Learning", "self supervised": "Self-Supervised Learning"}


@pytest.mark.parametrize("name", REPRESENTATION)
def test_each_representation_concept_is_registered_once_and_wired_like_the_earlier_expansions(name):
    from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner as Planner
    concepts = [c for c in ConceptRegistry().all() if c.name == name]
    assert len(concepts) == 1 and concepts[0].domain in {"deep_learning", "transformers"}  # a stable name, listed once
    assert name in ConceptExplanationEngine.EXPLANATIONS and name in QUIZ_BANK
    needs = PrerequisiteDetector.PREREQUISITE_RULES[name]
    assert needs and len(set(needs)) == len(needs)
    assert all(subject in Planner.STUDY_TIME and subject in Planner.STUDY_ORDER for subject in needs)  # only subjects with hours, resources and justifications


def test_the_registry_order_and_the_earlier_concepts_are_unchanged():
    names = [c.name for c in ConceptRegistry().all()]
    assert len(names) == len(set(names)) == 116  # 66 earlier concepts plus the 50 of concepts/ml_expansion.py
    assert names[52:60] == CLASSICAL and names[60:66] == REPRESENTATION  # appended: no existing concept moved
    assert {"Variational Autoencoder", "Fine-Tuning", "Contrastive Learning", "Embedding", "Large Language Model"} <= set(names)


def test_every_alias_resolves_to_its_concept_and_to_no_other():
    owners = {}
    for concept in ConceptRegistry().all():
        for term in (concept.name, *concept.aliases):
            owners.setdefault(term.lower(), set()).add(concept.name)
    for alias, concept in ALIASES.items():
        assert owners[alias.lower()] == {concept}
        assert concept in _detect(f"We rely on {alias} throughout.")


def test_prerequisite_relationships_resolve_and_the_rule_graph_stays_acyclic():
    rules = PrerequisiteDetector.PREREQUISITE_RULES
    state = {}

    def visit(name, trail):
        assert state.get(name) != "open", f"cycle: {' -> '.join([*trail, name])}"
        if state.get(name) == "done":
            return
        state[name] = "open"
        for target in rules.get(name, ()):
            visit(target, [*trail, name])
        state[name] = "done"

    for name in rules:
        visit(name, [])
    for name in REPRESENTATION:
        assert all(target in NAMES or target in rules or target in {t for v in rules.values() for t in v} for target in rules[name])
    assert "Transformer" in rules["Retrieval-Augmented Generation"] and rules["Self-Supervised Learning"] == ["Neural Networks"]


def test_representative_paper_text_triggers_the_right_concepts():
    paper = ("We train a compact student with knowledge distillation from a larger teacher. Our retrieval-augmented generation (RAG) system retrieves "
             "passages before answering, and decodes with beam search. A denoising autoencoder is pre-trained by self-supervised learning on unlabelled "
             "text, then transfer learning adapts it to the labelled task.")
    found = _detect(paper)
    assert set(REPRESENTATION) <= set(found)
    # each term counted once, as for every other concept; the name and its acronym written together are two mentions, like "graph neural network (GNN)"
    assert {name: found[name] for name in REPRESENTATION} == {**{n: 1 for n in REPRESENTATION}, "Retrieval-Augmented Generation": 2}, found


def test_ambiguous_and_incidental_wording_is_not_detected():
    text = ("Water distillation removes salt in a refinery column. A beam of light crossed the search area. The SSL certificate expired. "
            "The retrieval of a lost file and the transfer of funds were supervised by the teacher; the student learned alone. An encoder with auto gain "
            "handles the self-contained unit. Learning from transfer rates is unrelated.")
    assert not set(_detect(text)) & set(REPRESENTATION)


def test_existing_detection_is_unaffected_by_the_new_autoencoder_and_self_supervised_terms():
    found = _detect("A variational autoencoder and a VAE are trained with contrastive learning, fine-tuning and an embedding layer.")
    assert {"Variational Autoencoder", "Contrastive Learning", "Fine-Tuning", "Embedding"} <= set(found) and "Autoencoder" not in found
    assert found["Variational Autoencoder"] == 2
    assert "Self-Supervised Learning" in _detect("Self-supervised contrastive learning is used.") and "Contrastive Learning" in _detect("Self-supervised contrastive learning is used.")
