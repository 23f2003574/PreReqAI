"""Citation-aware programmes: papers that cite each other are ordered cited-first, every ordering decision names the reference that caused it, shared prerequisites and references are counted once, and unclear citations are never used."""
from datetime import date
from types import SimpleNamespace

import pytest

from backend import curriculum, paper_citations
from backend.models import PaperReference

pytestmark = pytest.mark.prereqai
A, B, C = "Efficient Transformers for Long Documents", "Attention Based Sequence Models Explained", "Foundations of Probabilistic Reasoning in Practice"


def session(sid, title, steps, references=()):
    report = {"paper": {"title": title}, "learning_plan": [{"concept": c, "estimated_hours": h} for c, h in steps], "missing_prerequisites": [{"concept": c, "importance": "essential"} for c, _ in steps],
              "study_progress": []}
    paper = SimpleNamespace(references=[PaperReference(i, text) for i, text in enumerate(references, start=1)])
    return SimpleNamespace(session_id=sid, report=report, paper_title=title, paper=paper)


def three(extra_refs=None):
    a = session("a", A, [("Calculus", 2.0)], [f"Smith, J. {B}. NeurIPS, 2020.", "Other, X. Something else entirely, 2019."])
    b = session("b", B, [("Probability", 5.0), ("Linear Algebra", 4.0)], [f"Lee, K. {C}. ICML, 2018.", f"Jones, Q. {C}. ICML, 2018 (extended version)."])
    c = session("c", C, [("Probability", 5.0), ("Statistics", 6.0)], ["Wu, T. Unrelated work on graphs. 2015."])
    return [a, b, c]


def test_papers_are_ordered_cited_first_even_when_their_hours_would_order_them_otherwise():
    plain = curriculum.build_curriculum([session("a", A, [("Calculus", 2.0)]), session("b", B, [("Probability", 5.0), ("Linear Algebra", 4.0)]), session("c", C, [("Probability", 5.0), ("Statistics", 6.0)])])
    assert plain["papers"][0]["title"] == A  # no citations: the cheapest paper first, as before
    result = curriculum.build_curriculum(three())
    assert [p["title"] for p in result["papers"]] == [C, B, A]


def test_each_ordering_decision_names_the_citation_and_its_reference_and_is_traceable():
    result = curriculum.build_curriculum(three())
    by_title = {p["title"]: p for p in result["papers"]}
    assert f"it cites {C!r} (its reference 1)" in by_title[B]["reason"] and f"it cites {B!r} (its reference 1)" in by_title[A]["reason"] and by_title[A]["cites"] == [B] and by_title[C]["cites"] == []
    ordering = {o["paper"]: o for o in result["citations"]["ordering"]}
    assert ordering[A]["after"] == B and ordering[A]["reference_number"] == 1 and B in ordering[A]["evidence"] and ordering[B]["after"] == C and len(result["citations"]["ordering"]) == 2


def test_shared_prerequisites_and_shared_references_are_counted_once():
    result = curriculum.build_curriculum(three())
    assert [s["concept"] for s in result["shared_prerequisites"]] == ["Probability"] and result["hours"]["combined"] == 2.0 + 5.0 + 4.0 + 6.0 and result["hours"]["saved_by_sharing"] == 5.0
    a, b = three()[:2]
    b.paper.references.append(PaperReference(3, a.paper.references[1].raw_text + " Appears in both papers' bibliographies."))
    a.paper.references[1].raw_text += " Appears in both papers' bibliographies."
    shared, totals = paper_citations.shared_references([a, b])
    assert len(shared) == 1 and sorted(shared[0]["papers"]) == ["a", "b"] and totals["total"] == 5 and totals["unique"] == 4


def test_ambiguous_short_self_and_cyclic_citations_are_never_used_for_ordering():
    a, b, c = three()
    a.paper.references = [PaperReference(1, f"Both: {B} and also {C}. 2021.")]  # one entry containing two analysed titles
    assert paper_citations.find_links([curriculum._paper_view(s) for s in (a, b, c)], [a, b, c])["ambiguous"][0]["papers"] == ["b", "c"]
    short = session("d", "Attention", [("Calculus", 1.0)], ["Vaswani. Attention is all you need. 2017."])
    other = session("e", "Another Paper About Optimisation Methods", [("Optimization", 3.0)], ["Vaswani. Attention is all you need. 2017."])
    links = paper_citations.find_links([curriculum._paper_view(s) for s in (short, other)], [short, other])
    assert links["links"] == [] and links["unmatchable"] == ["Attention"]
    own = session("f", C, [("Calculus", 1.0)], [f"Self: {C}. 2020."])
    assert paper_citations.find_links([curriculum._paper_view(own)], [own])["links"] == []
    x = session("x", A, [("Calculus", 2.0)], [f"{B}. 2020."])
    y = session("y", B, [("Probability", 5.0)], [f"{A}. 2021."])
    result = curriculum.build_curriculum([x, y])
    assert result["citations"]["cycles"] == [["x", "y"]] and result["citations"]["ordering"] == [] and len(result["papers"]) == 2


def test_the_calendar_still_schedules_the_combined_work_in_citation_order():
    result = curriculum.build_curriculum(three(), today=date(2026, 11, 20), deadline=date(2026, 12, 20), hours_per_day=3.0)
    assert [p["title"] for p in result["papers"]] == [C, B, A] and result["calendar"]["feasibility"]["status"] == "achievable"
    scheduled = [i["concept"] for d in result["calendar"]["days"] for i in d["items"]]
    assert scheduled.index("Probability") < scheduled.index("Calculus")  # the cited papers' groundwork comes first
