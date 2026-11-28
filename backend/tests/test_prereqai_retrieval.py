"""Hybrid retrieval: BM25 with section-role weighting behind the lexical search, measured on a question-to-passage benchmark, with quotations still exact."""
from types import SimpleNamespace

import pytest

from backend import retrieval
from backend.models import DetectedConcept, Paper, Paragraph, PaperSection
from backend.prereqai_eval import retrieval_benchmark
from backend.tutor import grounding

pytestmark = pytest.mark.prereqai
TOPICS = ["ferrous alloys", "tidal turbines", "glacial moraines", "coral bleaching", "mycorrhizal networks", "quartz crystals", "monsoon rainfall", "volcanic basalt", "lichen colonies",
          "estuarine sediment", "permafrost thawing", "bacterial plasmids", "stellar spectra", "seismic tomography", "alpine meadows", "kelp forests"]


CONCEPTS = ["Softmax", "Dropout", "Backpropagation", "Gradient Descent"]


def sentence(i):
    topic, other = TOPICS[i % len(TOPICS)], TOPICS[(i * 5 + 3) % len(TOPICS)]
    return f"We evaluate {CONCEPTS[i % len(CONCEPTS)].lower()} on {topic} in experiment number {i} and compare {other} against a calibrated reference."


def synthetic(roles=("1 Introduction", "2 Related Work", "3 Method", "4 Experiments")):
    paper = Paper(source_path="s.pdf", metadata=None)
    paper.paragraphs, pages = [], {}
    for p in range(1, 9):
        title = roles[p % len(roles)]
        text = " ".join(sentence(p * 3 + k) for k in range(3))
        paper.paragraphs.append(Paragraph(p, title, text, p))
        pages[p] = text
    paper.pages = [SimpleNamespace(page_number=n, text=t) for n, t in pages.items()]
    paper.sections = [PaperSection(title=t, content="x") for t in roles]
    paper.concepts = [DetectedConcept(name=name, domain="deep_learning", occurrences=6) for name in CONCEPTS]
    return paper


def test_bm25_ranks_by_matching_terms_and_every_passage_is_an_exact_quotation_of_its_page():
    paper = synthetic()
    found = retrieval.bm25_search(paper, "What happened with the stellar spectra and the seismic tomography?", 5)
    assert found and all(any(p["sentence"] in " ".join(page.text.split()) for page in paper.pages if page.page_number == p["page_number"]) for p in found)
    assert {"stellar", "seismic"} & set(found[0]["sentence"].split()) and len(found) == len({p["passage_id"] for p in found})
    assert retrieval.bm25_search(paper, "What about zzzz qqqq?", 5) == [] and retrieval.bm25_search(paper, "", 5) == []


def test_section_role_weighting_prefers_a_method_sentence_over_a_related_work_one_with_equal_matches():
    paper = Paper(source_path="s.pdf", metadata=None)
    same = "The sparse routing approach reduces memory pressure during long distributed training runs."
    paper.paragraphs = [Paragraph(1, "2 Related Work", same, 1), Paragraph(2, "3 Method", same.replace("sparse routing", "sparse routing"), 2)]
    paper.paragraphs[1].content = same + " "
    paper.pages = [SimpleNamespace(page_number=1, text=same), SimpleNamespace(page_number=2, text=same + " ")]
    found = retrieval.bm25_search(paper, "sparse routing memory pressure training", 5)
    assert [p["section"] for p in found[:2]] == ["3 Method", "2 Related Work"]  # equal matches: the instructional section ranks first


def test_hybrid_fuses_lexical_results_with_bm25_passages_by_reciprocal_rank(monkeypatch):
    paper = synthetic()
    lexical = [{"passage_id": "L1", "sentence": "x", "page_number": 1, "section": "s", "concepts": []}, {"passage_id": "L2", "sentence": "y", "page_number": 1, "section": "s", "concepts": []}]
    monkeypatch.setattr(grounding, "search_evidence", lambda paper, question, limit=4: list(lexical))
    fused = retrieval.hybrid_search(paper, "stellar spectra seismic", 4)
    assert [p["passage_id"] for p in fused][:1] == ["L1"] and {"L1", "L2"} <= {p["passage_id"] for p in fused}  # the lexical passages stay; BM25 passages are fused in as well
    monkeypatch.setattr(grounding, "search_evidence", lambda paper, question, limit=4: [])
    added = retrieval.hybrid_search(paper, "stellar spectra seismic tomography", 4)
    assert added and len(added) <= 4 and len({p["passage_id"] for p in added}) == len(added)


def test_the_benchmark_is_deterministic_names_no_concept_and_measures_both_systems_on_both_styles():
    paper = synthetic()
    first, second = retrieval_benchmark.make_questions(paper), retrieval_benchmark.make_questions(paper)
    assert first == second
    report = retrieval_benchmark.evaluate([paper])
    assert len(first) >= 6 and {q["style"] for q in first} == {"clean", "noisy", "loose"} and all(not any(name.lower() in q["question"].lower() for name in CONCEPTS) for q in first)
    assert report["questions"] == len(first) and set(report["systems"]) == {"lexical", "hybrid"} and set(report["styles"]) == {"clean", "noisy", "loose"}
    assert report["systems"]["hybrid"]["quotations_verified"] == 1.0 and report["systems"]["lexical"]["quotations_verified"] == 1.0
    assert report["systems"]["hybrid"]["recall_at_k"] >= report["systems"]["lexical"]["recall_at_k"]  # the hybrid never recalls less than the search it extends


def test_on_vague_questions_the_hybrid_recalls_more_than_the_lexical_search_it_extends():
    """Measured on this synthetic fixture (real-paper numbers come from the gate, see gate.retrieval_checks): clean and slightly noisy questions are solved by both, the loose ones only by BM25."""
    report = retrieval_benchmark.evaluate([synthetic()])
    lexical, hybrid = report["systems"]["lexical"]["recall_by_style"], report["systems"]["hybrid"]["recall_by_style"]
    assert lexical["clean"] == hybrid["clean"] == 1.0 and hybrid["loose"] > lexical["loose"] and hybrid["loose"] == 1.0
    assert report["systems"]["hybrid"]["recall_at_k"] > report["systems"]["lexical"]["recall_at_k"] and report["systems"]["hybrid"]["quotations_verified"] == 1.0


def test_the_gate_compares_hybrid_with_lexical_and_requires_exact_quotations(monkeypatch):
    from backend.prereqai_eval import gate, heldout

    monkeypatch.setattr(heldout, "load_manifest", lambda manifest=None: [{"pdf_path": "x.pdf"}])
    import backend.pipeline as pipeline

    monkeypatch.setattr(pipeline, "ResearchPaperPipeline", lambda: SimpleNamespace(run=lambda path: SimpleNamespace(paper=synthetic())))
    checks = []
    report = gate.retrieval_checks(checks)
    assert report and {c["metric"]: c["passed"] for c in checks} == {"hybrid_recall_not_below_lexical": True, "quotations_verified": True, "questions_generated": True}
    monkeypatch.setattr("backend.prereqai_eval.retrieval_benchmark.evaluate", lambda papers: {"questions": 12, "k": 5, "styles": {}, "systems": {
        "lexical": {"recall_at_k": 0.8, "quotations_verified": 1.0, "recall_by_style": {}}, "hybrid": {"recall_at_k": 0.7, "quotations_verified": 0.9, "recall_by_style": {}}}})
    broken = []
    gate.retrieval_checks(broken)
    assert [c["metric"] for c in broken if not c["passed"]] == ["hybrid_recall_not_below_lexical", "quotations_verified"]


def test_the_measurement_is_reproducible():
    assert retrieval_benchmark.evaluate([synthetic()]) == retrieval_benchmark.evaluate([synthetic()])


def test_equal_recalls_that_are_not_round_numbers_pass_and_the_report_agrees_with_itself(monkeypatch):
    """Regression (CI): 5/6 printed as 0.833 failed 'value >= threshold' against an unrounded 0.8333 lexical recall although the check had passed."""
    from backend.prereqai_eval import gate, heldout

    monkeypatch.setattr(heldout, "load_manifest", lambda manifest=None: [{"pdf_path": "x.pdf"}])
    import backend.pipeline as pipeline

    monkeypatch.setattr(pipeline, "ResearchPaperPipeline", lambda: SimpleNamespace(run=lambda path: SimpleNamespace(paper=synthetic())))
    system = {"recall_at_k": 5 / 6, "quotations_verified": 1.0, "recall_by_style": {}}
    monkeypatch.setattr("backend.prereqai_eval.retrieval_benchmark.evaluate", lambda papers: {"questions": 12, "k": 5, "styles": {}, "systems": {"lexical": dict(system), "hybrid": dict(system)}})
    checks = []
    gate.retrieval_checks(checks)
    assert all(c["passed"] and c["value"] >= c["threshold"] for c in checks)
