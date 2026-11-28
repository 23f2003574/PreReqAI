"""Equation-to-prose linking and the symbol glossary: exact quotations, equation references, lead-in sentences, "where X denotes" definitions."""
from types import SimpleNamespace

import pytest

from backend.parsing import equation_links

pytestmark = pytest.mark.prereqai


def test_equation_numbers_cited_by_a_sentence():
    assert equation_links.numbers_cited("This is Eq. 5, and see Eqs. (6) and 7.") >= {"5", "6"}
    assert equation_links.numbers_cited("In equation 12 we see") == {"12"} and equation_links.numbers_cited("no reference here") == set()


def test_definitions_are_found_with_their_symbol_meaning_and_sentence():
    match = equation_links._DEFINES.search("where σ is the logistic function.")
    assert match.group("first") == "σ" and match.group("meaning") == "the logistic function"


def test_glossary_merges_a_symbol_across_equations():
    entry = {"symbol": "β", "meaning": "a temperature", "sentence": "s", "page_number": 1, "section": "x"}
    links = {1: {"references": [], "introduction": None, "symbols": [entry]}, 2: {"references": [], "introduction": None, "symbols": [entry]}}
    assert equation_links.glossary(links) == [{**entry, "equations": [1, 2]}]


def test_a_paper_without_equations_has_no_links():
    assert equation_links.link(SimpleNamespace(equations=[], paragraphs=[1])) == {}


def test_dpo_equations_are_linked_to_cited_sentences_and_all_quotations_are_exact():
    from backend.platform import platform
    from backend.prereqai_eval import retrieval_real
    from backend.session import session_manager

    session = session_manager.get(platform.analyze(retrieval_real.pdf_paths({"dpo"})["dpo"])["session_id"])
    report = session.report
    pages = {p.page_number: " ".join(p.text.split()) for p in session.paper.pages}
    tagged = [e for e in report["equations"] if e["tag"]]
    linked = [e for e in tagged if e["references"] or e["introduction"] or e["symbols"]]
    assert len(tagged) >= 21 and len(linked) / len(tagged) >= 0.8
    quotes = [q for e in report["equations"] for q in [*e["references"], e["introduction"], *e["symbols"]] if q]
    quotes += report["symbol_glossary"]
    assert quotes and all(" ".join(q["sentence"].split()) in pages[q["page_number"]] for q in quotes)
    assert any(item["symbol"] == "σ" for item in report["symbol_glossary"])
