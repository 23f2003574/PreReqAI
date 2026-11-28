"""Contribution, background and incidental concept roles, background prerequisites, and fragment candidates. The real-paper prerequisite labels are AI-written and PROVISIONAL."""
import pytest

from backend.concepts import candidate_terms
from backend.prerequisites import concept_roles

pytestmark = pytest.mark.prereqai


def test_dpo_contribution_is_not_a_prerequisite_and_carries_its_quotation():
    from backend.prereqai_eval import gate

    paper = gate._real_papers({"dpo"})["dpo"]
    role = paper.concept_roles["Direct Preference Optimization"]
    assert role["role"] == "contribution" and role["evidence"] and role["evidence"][0]["sentence"]
    assert "Direct Preference Optimization" not in {p.concept for p in paper.prerequisites}


def test_related_work_only_concepts_are_incidental_in_a_full_paper():
    from backend.prereqai_eval import gate

    paper = gate._real_papers({"chain-of-thought"})["chain-of-thought"]
    assert paper.concept_roles["Graph Neural Network"]["role"] == "incidental" and paper.concept_roles["Reinforcement Learning"]["role"] == "incidental"
    assert paper.concept_roles["Chain-of-Thought"]["role"] == "contribution"


def test_a_background_concept_used_but_not_defined_becomes_a_background_prerequisite():
    from backend.prereqai_eval import gate

    paper = gate._real_papers({"dpo"})["dpo"]
    background = [p for p in paper.prerequisites if p.provenance == "background"]
    assert background and all(p.dependent_mentions >= concept_roles.BACKGROUND_MENTIONS for p in background)
    assert "Reinforcement Learning" in {p.concept for p in background}


def test_real_paper_prerequisite_precision_and_recall_both_improve_and_recall_never_drops():
    from backend.prereqai_eval import gate, prerequisite_eval

    data = prerequisite_eval.load()
    report = prerequisite_eval.evaluate(gate._real_papers(set(data["papers"])), data)
    assert report["precision"] >= 0.436 + 0.03 and report["recall"] >= 0.459 + 0.08 and report["status"] == "provisional"


def test_a_fragment_of_a_known_term_is_not_proposed_as_a_new_concept():
    known = {"large language model"}
    assert candidate_terms._part_of_known("large language", known) and not candidate_terms._part_of_known("language model quality", known)


def test_a_short_document_has_no_incidental_concepts():
    from types import SimpleNamespace

    paper = SimpleNamespace(metadata=SimpleNamespace(title="T"), paragraphs=[], sections=[], concepts=[SimpleNamespace(name="Dropout", occurrences=1)])
    assert concept_roles.classify(paper)["Dropout"]["role"] == "background"
