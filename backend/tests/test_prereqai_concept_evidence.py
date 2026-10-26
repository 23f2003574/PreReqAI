"""The report shows the evidence behind each detected concept, so the detection can be checked against the paper."""
from backend.platform import platform
from backend.reporting.learning_report_generator import LearningReportGenerator

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def test_report_lists_evidence_for_every_detected_concept():
    report = platform.analyze(SAMPLE)["report"]
    evidence = report["concept_evidence"]

    assert [item["concept"] for item in evidence].count("Attention") == 1
    assert {item["concept"] for item in evidence} == set(report["concepts"])
    assert all(item["occurrences"] >= 1 and item["domain"] for item in evidence)


def test_evidence_is_ordered_by_mentions_and_flags_single_mentions():
    paper = type("P", (), {})()
    paper.concepts = [type("C", (), {"name": n, "domain": "d", "occurrences": o})() for n, o in (("A", 1), ("B", 5), ("C", 3))]
    evidence = LearningReportGenerator._concept_evidence(paper)

    assert [(e["concept"], e["occurrences"], e["mentioned_once"]) for e in evidence] == [("B", 5, False), ("C", 3, False), ("A", 1, True)]


def test_sample_paper_evidence_is_exactly_what_the_pdf_says():
    evidence = platform.analyze(SAMPLE)["report"]["concept_evidence"]
    assert [(e["concept"], e["domain"], e["occurrences"], e["mentioned_once"]) for e in evidence] == [
        ("Attention", "transformers", 4, False),
        ("Softmax", "transformers", 3, False),
        ("Gradient Descent", "deep_learning", 2, False),
        ("Transformer", "transformers", 1, True),
        ("Backpropagation", "deep_learning", 1, True),
    ]


def test_bibliography_mentions_are_not_counted_from_a_real_pdf(tmp_path):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    lines = [("A Study of Things", 20), ("1 Introduction", 14),
             ("We apply the softmax function twice. The softmax output is normalised. Dropout is used once.", 10),
             ("References", 14),
             ("[1] Graph attention networks. Policy gradient methods. Softmax revisited. Dropout again.", 10)]
    for row, (text, size) in enumerate(lines):
        page.insert_text((72, 72 + 30 * row), text, fontsize=size)
    path = tmp_path / "paper.pdf"
    document.save(str(path))

    outcome = platform.analyze(str(path))

    assert outcome["status"] == "success"
    assert [(e["concept"], e["occurrences"], e["mentioned_once"]) for e in outcome["report"]["concept_evidence"]] == [
        ("Softmax", 2, False),  # the cited title "Softmax revisited" is not a third mention
        ("Dropout", 1, True),
    ]
    assert set(outcome["report"]["concepts"]) == {"Softmax", "Dropout"}  # cited Graph Attention Network / Policy Gradient absent
