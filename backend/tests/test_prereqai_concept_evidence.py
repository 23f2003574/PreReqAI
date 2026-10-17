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
