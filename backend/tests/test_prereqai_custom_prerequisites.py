"""Prerequisites for the learner's own concepts: proposed with the paper's sentence, never planned until confirmed, stored in a migrating versioned file."""
import json

import pytest

from backend import custom_concepts
from backend.concepts.custom_prerequisites import propose
from backend.models import Paper, Paragraph
from backend.models.concept import DetectedConcept
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai
TEXT = [
    ("1 Introduction", "Genetic drift is defined in terms of probability and random sampling of alleles. Allele frequency change builds on natural selection."),
    ("2 Background", "Gene flow moves alleles between populations. Our analysis of genetic drift, which we plot in the third figure of the appendix and discuss at length, requires Calculus."),
    ("References", "Smith. Genetic drift builds on probability. 1999."),
]


def paper():
    result = Paper(source_path="bio.pdf", metadata=None)
    result.paragraphs = [Paragraph(i, title, text, i) for i, (title, text) in enumerate(TEXT, start=1)]
    return result


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("PREREQAI_PROFILE_DIR", raising=False)
    monkeypatch.setenv(custom_concepts.ENV, str(tmp_path / "custom.json"))
    return tmp_path / "custom.json"


def test_a_stated_prerequisite_is_proposed_with_its_sentence_page_and_section_and_nothing_else(store):
    custom_concepts.add("Genetic drift")
    custom_concepts.add("Allele frequency change")
    found = propose(paper())
    keys = {(f["concept"], f["prerequisite"]) for f in found}
    assert ("Genetic drift", "Probability") in keys
    drift = next(f for f in found if f["concept"] == "Genetic drift" and f["prerequisite"] == "Probability")
    assert drift["page_number"] == 1 and drift["section"] == "1 Introduction" and "defined in terms of probability" in drift["sentence"] and drift["confirmed"] is False
    assert ("Allele frequency change", "Natural Selection") not in keys  # natural selection is not something PreReqAI has study material for
    assert all(f["section"] != "References" for f in found)  # the bibliography is never a source
    assert not any(f["prerequisite"] == "Calculus" for f in found)  # the cue is too far from the concept: not guessed


def test_without_confirmed_concepts_or_with_a_confirmed_edge_there_is_nothing_to_propose(store):
    assert propose(paper()) == []
    custom_concepts.add("Genetic drift")
    custom_concepts.add_prerequisite("Genetic drift", "probability", "q", 1, "1 Introduction")
    assert not any(f["prerequisite"] == "Probability" for f in propose(paper()))


def test_confirming_validates_and_stores_the_edge_with_its_quote(store):
    custom_concepts.add("Genetic drift")
    edge = custom_concepts.add_prerequisite("Genetic drift", "probability", "Genetic drift is defined in terms of probability", 1, "1 Introduction")
    assert edge["name"] == "Probability" and edge["page_number"] == 1 and custom_concepts.confirmed_rules() == {"Genetic drift": ["Probability"]}
    for concept, target in [("Genetic drift", "Probability"), ("Genetic drift", "Genetic drift"), ("Genetic drift", "Underwater Basket Weaving"), ("Nope", "Calculus")]:
        with pytest.raises(custom_concepts.CustomConceptError):
            custom_concepts.add_prerequisite(concept, target)
    assert custom_concepts.remove_prerequisite("Genetic drift", "Probability") is True and custom_concepts.confirmed_rules() == {} and custom_concepts.remove_prerequisite("Genetic drift", "Probability") is False


def test_a_version_1_store_is_read_and_rewritten_as_version_2_without_losing_anything(store):
    store.write_text(json.dumps({"format": custom_concepts.FORMAT, "schema_version": 1, "concepts": [{"name": "Genetic drift", "aliases": ["GD drift"], "definition": "d", "confirmed_on": "2026-11-01"}]}))
    concepts, problem = custom_concepts.load()
    assert problem == "" and concepts[0]["prerequisites"] == [] and concepts[0]["aliases"] == ["GD drift"]
    custom_concepts.add_prerequisite("Genetic drift", "Calculus")
    saved = json.loads(store.read_text())
    assert saved["schema_version"] == 2 and saved["concepts"][0]["definition"] == "d" and saved["concepts"][0]["prerequisites"][0]["name"] == "Calculus"
    store.write_text(json.dumps({**saved, "schema_version": 3}))
    assert custom_concepts.load()[1].startswith("the custom concept store")


def plan_for(names):
    result = paper()
    result.concepts = [DetectedConcept(name=n, domain="custom", occurrences=3) for n in names]
    return PrerequisiteDetector().detect(result)


def test_only_confirmed_edges_reach_the_plan(store):
    custom_concepts.add("Genetic drift")
    assert plan_for(["Genetic drift"]).prerequisites == []  # no rules: unknown, not absent
    assert "Genetic drift" in plan_for(["Genetic drift"]).concepts_without_rules
    propose(paper())  # a proposal changes nothing
    assert plan_for(["Genetic drift"]).prerequisites == []
    custom_concepts.add_prerequisite("Genetic drift", "Probability", "q")
    planned = plan_for(["Genetic drift"])
    assert [p.concept for p in planned.prerequisites] == ["Probability"] and planned.concepts_without_rules == []
