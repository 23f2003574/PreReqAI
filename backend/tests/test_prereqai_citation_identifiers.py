"""Citations are matched by DOI, arXiv identifier and author-year-title as well as title, with the method reported and ambiguity never guessed."""
from types import SimpleNamespace

import pytest

from backend import curriculum, paper_citations
from backend.models import PaperReference

pytestmark = pytest.mark.prereqai
A, B, C = "Efficient Transformers for Long Documents", "Attention Based Sequence Models Explained", "Foundations of Probabilistic Reasoning in Practice"


def session(sid, title, references=(), page_text="", author="", steps=(("Calculus", 2.0),)):
    report = {"paper": {"title": title}, "learning_plan": [{"concept": c, "estimated_hours": h} for c, h in steps], "missing_prerequisites": [{"concept": c, "importance": "essential"} for c, _ in steps], "study_progress": []}
    paper = SimpleNamespace(references=[PaperReference(i, text) for i, text in enumerate(references, start=1)], pages=[SimpleNamespace(text=page_text)], metadata=SimpleNamespace(author=author))
    return SimpleNamespace(session_id=sid, report=report, paper_title=title, paper=paper)


def views(*sessions):
    return [{"session_id": s.session_id, "title": s.paper_title} for s in sessions]


def link_of(links, citing):
    return next((x for x in links["links"] if x["citing"] == citing), None)


def test_a_reference_with_only_a_doi_links_by_doi():
    cited = session("b", B, page_text="Attention Based Sequence Models Explained. https://doi.org/10.1234/abc.5678 Abstract")
    citing = session("a", A, ["Lee, K. A different heading entirely. doi:10.1234/ABC.5678."])
    found = paper_citations.find_links(views(citing, cited), [citing, cited])
    assert link_of(found, "a")["cited"] == "b" and link_of(found, "a")["method"] == "doi"


def test_a_reference_with_only_an_arxiv_identifier_links_by_arxiv_whatever_the_version():
    cited = session("b", "Short", page_text="arXiv:1706.03762v5 [cs.CL] 6 Dec 2017 Attention")
    citing = session("a", A, ["Vaswani et al. 2017. arXiv preprint arXiv:1706.03762v1."])
    found = paper_citations.find_links(views(citing, cited), [citing, cited])
    assert link_of(found, "a")["method"] == "arxiv_id" and found["unmatchable"] == []  # a short title is matchable through its identifier


def test_an_abbreviated_title_links_by_author_year_and_title_words_but_a_wrong_year_or_author_does_not():
    cited = session("d", "Efficient Transformers for Long Documents Analysis", page_text="arXiv:2001.12345v2 [cs.LG]", author="Jane Smith; Bo Lee")
    ok = session("a", A, ["Smith, J. Efficient transformers long documents analysis. 2020."])
    wrong_year = session("b", B, ["Smith, J. Efficient transformers long documents analysis. 2012."])
    wrong_author = session("c", C, ["Brown, J. Efficient transformers long documents analysis. 2020."])
    found = paper_citations.find_links(views(ok, wrong_year, wrong_author, cited), [ok, wrong_year, wrong_author, cited])
    assert link_of(found, "a")["method"] == "author_year_title" and link_of(found, "b") is None and link_of(found, "c") is None


def test_a_reference_matching_two_papers_by_identifier_is_ambiguous_and_not_used():
    one, two = session("b", B, page_text="doi 10.1111/one"), session("c", C, page_text="doi 10.1111/two")
    citing = session("a", A, ["Both works: 10.1111/one and 10.1111/two together."])
    found = paper_citations.find_links(views(citing, one, two), [citing, one, two])
    assert found["links"] == [] and found["ambiguous"][0]["method"] == "doi" and sorted(found["ambiguous"][0]["papers"]) == ["b", "c"]


def test_the_existing_title_matching_is_unchanged_and_unrelated_references_add_no_links():
    b = session("b", B)
    a = session("a", A, [f"Smith, J. {B}. NeurIPS, 2020.", "Other, X. Something else entirely, 2019."])
    found = paper_citations.find_links(views(a, b), [a, b])
    assert [(x["citing"], x["cited"], x["method"], x["reference_number"]) for x in found["links"]] == [("a", "b", "title", 1)]
    assert found["unmatchable"] == [] and paper_citations.find_links(views(b, a), [b, a])["links"][0]["method"] == "title"
    short = session("s", "Attention")
    assert paper_citations.find_links(views(a, short), [a, short])["unmatchable"] == ["Attention"]


def test_an_identifier_only_citation_orders_the_programme_and_names_its_method():
    cited = session("b", B, page_text="DOI 10.5555/xyz.1", steps=(("Probability", 5.0),))
    citing = session("a", A, ["Lee. Unrelated words. 10.5555/xyz.1"], steps=(("Calculus", 1.0),))
    result = curriculum.build_curriculum([citing, cited])
    assert [p["title"] for p in result["papers"]] == [B, A] and result["citations"]["ordering"][0]["method"] == "doi" and "matched by doi" in result["papers"][1]["reason"]


@pytest.mark.parametrize("reference", [
    "Vaswani et al. 2017. arXiv preprint arXiv:1706.03762v1.",
    "Vaswani, A. et al. Attention is all you need. https://arxiv.org/abs/1706.03762",
    "Vaswani, A. et al. https://arxiv.org/pdf/1706.03762v7.pdf",
    "Vaswani, A. et al. doi:10.48550/arXiv.1706.03762",
    "Vaswani, A. et al. arXiv.org, 1706.03762, 2017.",
    "Vaswani, A. et al. arXiv 1706.03762.",
])
def test_every_common_form_of_an_arxiv_reference_links_by_identifier(reference):
    cited = session("b", "Short", page_text="arXiv:1706.03762v5 [cs.CL] 6 Dec 2017 Attention")
    citing = session("a", A, [reference])
    found = paper_citations.find_links(views(citing, cited), [citing, cited])
    assert link_of(found, "a") is not None and link_of(found, "a")["cited"] == "b" and link_of(found, "a")["method"] in ("arxiv_id", "doi")


def test_a_bare_number_or_a_longer_identifier_is_not_an_arxiv_reference():
    assert paper_citations._arxiv("see 1706.03762 in the table") == set()
    assert paper_citations._arxiv("arXiv:1706.037621") == set()
    assert paper_citations._arxiv("arXiv:cs/0112017v2 and arxiv.org/abs/hep-th/9901001") == {"cs/0112017", "hep-th/9901001"}
