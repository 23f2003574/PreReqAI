"""The regression gate: it passes on the shipped data, fails on a real regression with an actionable report, keeps real-paper scores provisional until a human approves, and never counts pending or AI-only approvals as human-reviewed."""
import json
import shutil

import pytest

from backend.parsing import scientific_section_parser
from backend.prereqai_eval import benchmark, gate
from backend.prereqai_eval.__main__ import main

pytestmark = pytest.mark.prereqai


@pytest.fixture(scope="module")
def shipped():
    return gate.run_gate()


def check(report, group, metric):
    return next(c for c in report["checks"] if c["group"] == group and c["metric"] == metric)


def test_the_gate_passes_on_the_shipped_pipeline_and_covers_every_group(shipped):
    assert shipped["passed"] and {c["group"] for c in shipped["checks"]} == {"text_fixtures", "synthetic_pdf", "synthetic_evidence", "real_papers_provisional", "mastery_simulation", "heldout_invariants", "retrieval", "prerequisite_graph", "math_subtopics", "retrieval_real", "math_real"}
    assert all(c["value"] >= c["threshold"] for c in shipped["checks"]) and len(shipped["checks"]) >= 20
    assert check(shipped, "synthetic_evidence", "exact_quotation")["value"] == 1.0 and check(shipped, "real_papers_provisional", "evaluated_papers")["value"] == 3


def test_the_thresholds_file_names_every_metric_the_gate_checks():
    floors = gate.load_thresholds()
    assert floors["format"] == "prereqai-gate-thresholds" and all(0 < v <= 3 for group in ("text_fixtures", "synthetic_pdf", "synthetic_evidence", "real_papers_provisional") for v in floors[group].values())
    with pytest.raises(ValueError):
        gate.load_thresholds(gate.Path(gate.__file__))  # not a thresholds file


def test_a_real_regression_fails_the_gate_with_the_names_of_what_went_wrong(monkeypatch):
    monkeypatch.setattr(scientific_section_parser, "layout_headings", lambda pages: [])  # typography is no longer used to find headings
    report = gate.run_gate()
    failed = [c for c in report["checks"] if not c["passed"]]
    assert not report["passed"] and any(c["group"] == "real_papers_provisional" and c["metric"] == "headings_f1" for c in failed)
    headings = check(report, "real_papers_provisional", "headings_f1")
    assert headings["value"] < headings["threshold"] and "dpo" in headings["detail"] and "missed" in headings["detail"]  # the false negatives, by paper
    text = gate.render_gate(report)
    assert "REGRESSION GATE: FAILED" in text and "[FAIL]" in text and "what to look at:" in text and "thresholds.json" in text


def test_the_command_line_exits_non_zero_on_a_missed_floor_and_zero_otherwise(monkeypatch, capsys):
    strict = gate.load_thresholds()
    strict["synthetic_pdf"]["headings_f1"] = 1.01  # unreachable
    monkeypatch.setattr(gate, "load_thresholds", lambda *a, **k: strict)
    assert main(["--gate"]) == 1 and "FAILED" in capsys.readouterr().out
    monkeypatch.undo()
    assert main(["--gate"]) == 0 and "PASSED" in capsys.readouterr().out


def test_real_paper_scores_are_provisional_while_the_approvals_are_an_ais(shipped):
    real = shipped["real_papers"]
    assert real["status"] == "provisional" and real["human_reviewed"] is None and real["provisional"]["paper_ids"] == ["dpo", "mixtral", "chain-of-thought"]
    assert {p["review_kind"] for p in real["per_paper"]} == {"ai"} and "PROVISIONAL" in gate.render_gate(shipped)
    report = benchmark.evaluate_benchmark()
    assert report["status"] == "provisional" and "PROVISIONAL" in benchmark.render_benchmark(report) and report["human_reviewed"] is None


@pytest.fixture
def one_paper(tmp_path):
    """A copy of the benchmark holding only the Mixtral paper (fast), to approve, edit and score without touching the shipped data."""
    target = tmp_path / "benchmark"
    shutil.copytree(benchmark.BENCHMARK_DIR, target, ignore=shutil.ignore_patterns("dpo.pdf", "chain-of-thought.pdf"))
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["papers"] = [p for p in manifest["papers"] if p["id"] == "mixtral"]
    (target / "manifest.json").write_text(json.dumps(manifest))
    return target


def test_only_a_humans_approval_makes_a_paper_human_reviewed_and_pending_or_unlabelled_ones_never_do(one_paper):
    annotation = one_paper / "annotations" / "mixtral.json"
    data = json.loads(annotation.read_text())
    data["review"] = {"status": "pending_review"}
    annotation.write_text(json.dumps(data))
    assert benchmark.evaluate_benchmark(one_paper / "manifest.json")["counts"]["evaluated"] == 0  # pending: not scored at all
    data["review"] = {"status": "approved", "reviewer": "Someone", "reviewed_on": "2026-11-20"}  # approved before the kind was recorded
    annotation.write_text(json.dumps(data))
    assert benchmark.review_kind(data) == "ai" and benchmark.evaluate_benchmark(one_paper / "manifest.json")["status"] == "provisional"
    benchmark.approve(annotation, "An AI", kind="ai")
    assert benchmark.evaluate_benchmark(one_paper / "manifest.json")["human_reviewed"] is None
    benchmark.approve(annotation, "A. Human Reviewer")  # the default kind is human
    report = benchmark.evaluate_benchmark(one_paper / "manifest.json")
    assert report["status"] == "human_reviewed" and report["human_reviewed"]["paper_ids"] == ["mixtral"] and report["provisional"] is None
    assert json.loads(annotation.read_text())["review"]["reviewer_kind"] == "human" and "PROVISIONAL" not in benchmark.render_benchmark(report)
    with pytest.raises(benchmark.BenchmarkError):
        benchmark.approve(annotation, "x", kind="robot")


def test_the_command_line_records_who_approved(one_paper, capsys):
    annotation = str(one_paper / "annotations" / "mixtral.json")
    assert main(["--approve", annotation, "--reviewer", "A Person", "--reviewer-kind", "ai"]) == 0
    assert json.loads(open(annotation).read())["review"]["reviewer_kind"] == "ai"
    assert main(["--approve", annotation, "--reviewer", "A Person"]) == 0 and json.loads(open(annotation).read())["review"]["reviewer_kind"] == "human"


def test_prerequisite_coverage_is_scored_once_it_is_annotated(one_paper):
    annotation = one_paper / "annotations" / "mixtral.json"
    data = json.loads(annotation.read_text())
    data["prerequisites"] = [{"concept": "Probability", "covered": False}, {"concept": "Neural Networks", "covered": False}, {"concept": "Linear Algebra", "covered": False}]
    annotation.write_text(json.dumps(data))
    report = benchmark.evaluate_benchmark(one_paper / "manifest.json")
    row = report["papers"][0]
    assert row["coverage"] is not None and {"precision", "recall", "f1", "tp", "fp", "fn"} <= set(row["coverage"]) and report["coverage"] is not None
    assert "coverage P=" in benchmark.render_benchmark(report)
