"""Candidate-term filtering, scored on AI-written PROVISIONAL labels (backend/prereqai_eval/candidate_labels.json) of the baseline top-20 candidates of the six real papers."""
import json
from pathlib import Path

import pytest

from backend.concepts import candidate_terms as ct

pytestmark = pytest.mark.prereqai
LABELS = json.loads((Path(__file__).resolve().parents[1] / "prereqai_eval" / "candidate_labels.json").read_text(encoding="utf-8"))["papers"]
BASELINE_PRECISION = 37 / 114  # every labelled candidate accepted, as before the filter


def _scores():
    tp = fp = fn = 0
    for terms in LABELS.values():
        for term, label in terms.items():
            accepted = ct.accepts(term)
            tp += accepted and label == "term"
            fp += accepted and label != "term"
            fn += (not accepted) and label == "term"
    return tp / (tp + fp), tp / (tp + fn), tp, fp, fn


def test_the_filter_is_measurably_more_precise_than_accepting_everything():
    precision, recall, tp, fp, fn = _scores()
    # measured 0.466 precision (34 of 73 accepted are terms) at 0.919 recall; the filter removes 41 of 77 non-terms and 3 of 37 terms, and the remaining noise is generic noun phrases it cannot tell from terms
    assert precision >= 0.45 > BASELINE_PRECISION and recall >= 0.9, (precision, recall, tp, fp, fn)


@pytest.mark.parametrize("term", ["outperforms llama", "gqa achieves", "mixtral outperforms", "achieves quality close", "matches llama"])
def test_clause_fragments_with_a_finite_verb_are_rejected(term):
    assert not ct.accepts(term)


@pytest.mark.parametrize("term", ["keys and values", "mqa and gqa", "key and value", "summarization and dialogue"])
def test_conjunctions_of_two_things_are_rejected(term):
    assert not ct.accepts(term)


@pytest.mark.parametrize("term", ["prior work", "inter alia", "superior performance", "united states", "atten- tion"])
def test_academic_filler_and_cut_words_are_rejected(term):
    assert not ct.accepts(term)


@pytest.mark.parametrize("term", ["Large Language Models", "chain of thought", "reward models", "Layer Normalisation", "Self Attention"])
def test_plurals_and_spelling_variants_of_registry_concepts_are_known(term):
    assert not ct.accepts(term)


@pytest.mark.parametrize("term", ["sliding window", "partition function", "red teaming", "rolling buffer cache", "query heads"])
def test_genuine_terms_are_still_proposed(term):
    assert ct.accepts(term)


def test_a_definition_cue_candidate_survives():
    class P:
        def __init__(self, content):
            self.content, self.section_title, self.page_number, self.paragraph_id = content, "1 Introduction", 1, "p1"

    paper = type("Paper", (), {"paragraphs": [P("The partition function (PF) is intractable. The so-called red teaming protocol is used.")]})()
    terms = {c["term"] for c in ct.find(paper)}
    assert "partition function" in terms and any(t.startswith("red teaming") for t in terms)
