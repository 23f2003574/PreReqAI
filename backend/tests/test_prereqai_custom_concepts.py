"""Concepts beyond the registry: a biology paper surfaces candidate terms with their sentences, nothing enters the analysis until the learner confirms it, and a confirmed concept is detected afterwards."""
import json
import multiprocessing

import pytest

from backend import custom_concepts
from backend.concepts.candidate_terms import find
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph

pytestmark = pytest.mark.prereqai
TEXT = [
    ("1 Introduction", "Populations change over generations. Natural selection (NS) favours heritable traits that improve survival. We call the spread of such traits allele frequency change, and genetic drift "
                       "(GD) is the random component of that change."),
    ("2 Background", "Genetic drift has a stronger effect in small populations. Gene flow, also known as migration, moves alleles between populations. Natural selection acts on phenotypes, "
                     "while genetic drift acts on allele frequencies."),
    ("3 Methods", "We simulate gene flow between two islands and measure allele frequency after each generation. The Hardy-Weinberg equilibrium (HWE) is the expected state without selection."),
    ("4 Results", "Allele frequency changed fastest where gene flow was weak. The Hardy-Weinberg equilibrium was violated whenever natural selection was strong. Genetic drift explained the rest."),
    ("References", "Smith. Natural selection and genetic drift. 1999. Natural selection natural selection natural selection."),
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


def test_a_non_machine_learning_paper_surfaces_at_least_five_relevant_candidates_with_their_sentences():
    found = find(paper())
    terms = {c["term"].lower() for c in found}
    assert len(found) >= 5 and {"natural selection", "genetic drift", "gene flow", "allele frequency", "hardy-weinberg equilibrium"} <= terms, terms
    top = {c["term"].lower(): c for c in found}
    assert "abbreviation (NS)" in top["natural selection"]["reason"] and top["natural selection"]["page_number"] == 1 and "Natural selection (NS)" in top["natural selection"]["sentence"]
    assert all(c["sentence"] and c["section"] != "References" and c["mentions"] >= 1 for c in found) and found == sorted(found, key=lambda c: (-c["score"], c["term"]))
    assert not any(c["term"].lower().startswith(("the ", "we ")) for c in found)


def test_terms_the_registry_knows_and_function_word_phrases_are_never_candidates():
    machine = Paper(source_path="m.pdf", metadata=None)
    machine.paragraphs = [Paragraph(1, "1 Intro", "Gradient descent trains the network. The gradient descent update uses the learning rate. We use gradient descent again and gradient descent twice.", 1),
                          Paragraph(2, "2 Method", "Softmax outputs probabilities. The softmax layer follows. We apply softmax once more with gradient descent.", 2)]
    assert [c for c in find(machine) if "gradient descent" in c["term"].lower() or "softmax" in c["term"].lower()] == []


def test_nothing_enters_the_analysis_until_the_learner_confirms_it_and_then_it_is_detected(store):
    unconfirmed = RuleBasedConceptDetector().detect(paper())
    assert [c.name for c in unconfirmed.concepts] == []  # candidates are only suggestions
    entry = custom_concepts.add("Genetic Drift", ["genetic-drift"], "Random change in allele frequencies.")
    assert entry["name"] == "Genetic Drift" and json.loads(store.read_text())["schema_version"] == 1
    confirmed = RuleBasedConceptDetector().detect(paper())
    names = {c.name: c for c in confirmed.concepts}
    assert "Genetic Drift" in names and names["Genetic Drift"].occurrences >= 3 and names["Genetic Drift"].domain == "custom"
    assert "Genetic Drift" not in {c["term"] for c in find(paper(), {t.lower() for c in __import__("backend.concepts.concept_registry", fromlist=["x"]).ConceptRegistry(custom=True).all() for t in (c.name, *c.aliases)})}
    assert custom_concepts.remove("genetic drift") is True and custom_concepts.remove("genetic drift") is False
    assert [c.name for c in RuleBasedConceptDetector().detect(paper()).concepts] == []


def test_the_store_refuses_duplicates_bad_names_and_a_missing_location(store, monkeypatch):
    custom_concepts.add("Gene Flow")
    for bad, message in (("gene flow", "already a concept"), ("Softmax", "already a concept"), ("x", "not a valid concept name"), ("a<script>b", "not a valid concept name")):
        with pytest.raises(custom_concepts.CustomConceptError) as error:
            custom_concepts.add(bad)
        assert message in str(error.value)
    monkeypatch.delenv(custom_concepts.ENV)
    with pytest.raises(custom_concepts.CustomConceptError, match="nowhere to keep it"):
        custom_concepts.add("Allele Frequency")
    assert custom_concepts.load() == ([], "")


def test_an_unusable_or_newer_store_is_reported_left_unchanged_and_detection_falls_back_to_the_registry(store):
    store.write_text(json.dumps({"format": custom_concepts.FORMAT, "schema_version": 9, "concepts": []}), encoding="utf-8")
    concepts, problem = custom_concepts.load()
    assert concepts == [] and "newer PreReqAI" in problem
    with pytest.raises(custom_concepts.CustomConceptError):
        custom_concepts.add("Gene Flow")
    assert json.loads(store.read_text())["schema_version"] == 9 and RuleBasedConceptDetector().detect(paper()).concepts == []
    store.write_text("{nope", encoding="utf-8")
    assert custom_concepts.load()[1].startswith("the custom concept store") and "not valid JSON" in custom_concepts.load()[1]


def test_a_version_one_store_written_by_hand_is_read_and_extended(store):
    store.write_text(json.dumps({"format": custom_concepts.FORMAT, "schema_version": 1, "concepts": [{"name": "Gene Flow", "aliases": ["migration"]}]}), encoding="utf-8")
    custom_concepts.add("Allele Frequency")
    saved = json.loads(store.read_text())
    assert [c["name"] for c in saved["concepts"]] == ["Gene Flow", "Allele Frequency"] and saved["concepts"][0]["aliases"] == ["migration"]


def _add(args):
    path, name = args
    import os

    os.environ[custom_concepts.ENV] = path
    custom_concepts.add(name)


def test_four_processes_adding_concepts_lose_none(store):
    names = ["Gene Flow", "Allele Frequency", "Founder Effect", "Genetic Bottleneck"]
    with multiprocessing.get_context("spawn").Pool(4) as pool:
        pool.map(_add, [(str(store), n) for n in names])
    assert sorted(c["name"] for c in custom_concepts.load()[0]) == sorted(names)


def test_a_repeated_phrase_that_crosses_punctuation_or_a_number_never_crashes_the_search():
    """Regression (CI, every real paper): word pairs built from separate tokens were looked up as a substring of the paragraph and raised StopIteration."""
    result = Paper(source_path="x.pdf", metadata=None)
    result.paragraphs = [Paragraph(i, "1 Intro", "The tidal model, 3 data points; (tidal model) and tidal model 3 data points again. Tidal energy, data.", i) for i in (1, 2, 3)]
    found = find(result)
    assert all(c["sentence"] for c in found) and "tidal model" in {c["term"].lower() for c in found}
