"""Prerequisites the paper states itself: cues, sentences with page and section, provenance, one grade up for explicit cues, and no edge from reminders or unknown topics."""
import json
from pathlib import Path

import pytest

from backend.models import Paper, Paragraph, Prerequisite
from backend.parsing import stated_prerequisites as stated

pytestmark = pytest.mark.prereqai
CASES = json.loads((Path(__file__).resolve().parents[1] / "prereqai_eval" / "fixtures" / "stated_prerequisites.json").read_text(encoding="utf-8"))["cases"]


def paper(*paragraphs, prerequisites=()):
    result = Paper(source_path="x.pdf", metadata=None)
    result.paragraphs = [Paragraph(i, title, text, page) for i, (title, text, page) in enumerate(paragraphs, start=1)]
    result.prerequisites = list(prerequisites)
    return result


def test_precision_and_recall_are_measured_on_the_annotated_sentences():
    """The sentences are written for this evaluation and annotated by an AI (pending human review), and the cue rules were adjusted against them: a floor, not an independent score."""
    assert len(CASES) >= 10
    score = stated.evaluate(CASES)
    assert score["cases"] == len(CASES) and score["tp"] >= 12 and score["precision"] >= 0.9 and score["recall"] >= 0.9, score


def test_an_explicit_statement_raises_the_grade_and_records_the_sentence():
    sentence = "We assume familiarity with linear algebra and basic probability theory."
    base = Prerequisite(concept="Linear Algebra", reason="Required to understand Attention", confidence=1.0, importance="essential", evidence_strength="weak", strength_reasons=["1 mention"])
    result = stated.apply(paper(("2 Background", sentence, 3), prerequisites=[base]))
    entry = {p.concept: p for p in result.prerequisites}["Linear Algebra"]
    assert entry.evidence_strength == "moderate" and entry.provenance == "inferred+stated"
    assert entry.stated_by_paper[0]["sentence"] == sentence and entry.stated_by_paper[0]["page_number"] == 3 and entry.stated_by_paper[0]["section"] == "2 Background"
    assert entry.evidence_note.startswith("The paper itself states this prerequisite")
    probability = {p.concept: p for p in result.prerequisites}["Probability"]  # not reached by the table here, but a subject the table uses: added, labelled as the paper's
    assert probability.provenance == "stated" and probability.importance == "supporting" and probability.evidence_strength == "moderate"


def test_a_reminder_an_unknown_topic_and_a_non_table_concept_create_no_prerequisite():
    result = stated.apply(paper(("1 Introduction", "Recall that the softmax function maps a vector of scores to a probability distribution.", 2),
                                ("1 Introduction", "We assume the reader is comfortable with the chess openings discussed by the authors.", 2),
                                ("1 Introduction", "We assume prior knowledge of Byzantine consensus protocols for the later sections.", 2),
                                ("1 Introduction", "Readers should be familiar with the Adam optimizer and its moment estimates.", 2)))
    assert [p.concept for p in result.prerequisites] == []  # the Adam optimizer is a concept the table does not use as a subject
    assert any(f["subject"] == "Softmax" and f["cue"] == "reminder" for f in result.stated_prerequisites)
    assert [u["cue"] for u in result.unmatched_prerequisite_cues] == ["explicit", "explicit"]  # the chess and Byzantine sentences: shown, never an edge


def test_a_reminder_gives_provenance_without_raising_the_grade_and_the_bibliography_is_ignored():
    base = Prerequisite(concept="Probability", reason="r", confidence=1.0, evidence_strength="weak")
    result = stated.apply(paper(("2 Background", "Recall that probability distributions must sum to one over the sample space.", 2),
                                ("References", "We assume familiarity with calculus and linear algebra, 2020.", 9), prerequisites=[base]))
    entry = result.prerequisites[0]
    assert entry.evidence_strength == "weak" and entry.provenance == "inferred+stated" and entry.stated_by_paper[0]["cue"] == "reminder"
    assert not any(f["section"] == "References" for f in result.stated_prerequisites)


def test_longer_terms_swallow_their_parts_and_inferred_prerequisites_stay_inferred():
    assert stated.find_in_sentence("Familiarity with self-attention is assumed.")["concepts"] == ["Self-Attention"]
    untouched = Prerequisite(concept="Calculus", reason="r", confidence=1.0, evidence_strength="strong")
    result = stated.apply(paper(("1 Introduction", "The model is trained with gradient descent and uses a softmax output layer.", 1), prerequisites=[untouched]))
    assert result.prerequisites[0].provenance == "inferred" and result.prerequisites[0].stated_by_paper == [] and result.stated_prerequisites == []
