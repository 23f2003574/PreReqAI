"""Real-paper benchmark infrastructure: manifest and annotation validation, review-state enforcement, metrics, the offline runner and the CLI."""
import copy
import hashlib
import json

import pytest

from backend.prereqai_eval import __main__ as cli
from backend.prereqai_eval import benchmark as bm
from backend.prereqai_eval.harness import evaluate
from backend.prereqai_eval.pdf_fixtures import FIXTURES, write_fixture_pdfs

pytestmark = pytest.mark.prereqai

ANNOTATION = {
    "format": bm.ANNOTATION_FORMAT, "schema_version": 1, "paper_id": "demo", "review": {"status": "pending_review"},
    "sections": [{"title": "Abstract", "role": "other"}, {"title": "Introduction", "role": "other"}, {"title": "Background", "role": "instructional"},
                 {"title": "Method", "role": "instructional"}, {"title": "Experiments on CIFAR-10", "role": "other"}, {"title": "Conclusion", "role": "other"},
                 {"title": "References", "role": "related"}],
    "concepts": [{"name": "Softmax", "occurrences": {"Method": 2}}, {"name": "Transformer"}, {"name": "Self-Attention"}],
    "prerequisites": [{"concept": "Linear Algebra", "covered": True}, {"concept": "Attention", "covered": True}, {"concept": "Probability", "covered": False}],
}


def _bench(tmp_path, status="approved", licence="verified"):
    """A tiny benchmark folder whose 'paper' is a generated PDF; it checks the machinery only and is not a real-paper result."""
    pdf = write_fixture_pdfs(tmp_path / "pdfs", [FIXTURES[0]])["numbered-1col"]
    annotation = copy.deepcopy(ANNOTATION)
    if status == "approved":
        annotation["review"] = {"status": "approved", "reviewer": "A. Reviewer", "reviewed_on": "2026-11-16"}
    (tmp_path / "annotations").mkdir()
    (tmp_path / "annotations" / "demo.json").write_text(json.dumps(annotation))
    paper = {"id": "demo", "title": "Demo", "authors": ["A. Author"], "source_url": "https://example.org/demo", "publication": {"venue": "Test", "year": 2026},
             "license": {"status": licence, "spdx": "CC-BY-4.0", "evidence_url": "https://example.org/licence", "verified_on": "2026-11-16"} if licence == "verified" else {"status": "unverified"},
             "retrieved_on": "2026-11-16", "pdf": {"path": "pdfs/numbered-1col.pdf", "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()},
             "annotation": "annotations/demo.json"}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"format": bm.MANIFEST_FORMAT, "schema_version": 1, "papers": [paper]}))
    return manifest


def test_the_bundled_manifest_is_valid_lists_five_papers_and_claims_no_unverified_licence():
    manifest = bm.load_manifest()
    assert len(manifest["papers"]) >= 5 and all(p["license"]["status"] == "unverified" and p["pdf"] is None for p in manifest["papers"])
    report = bm.evaluate_benchmark()
    assert report["counts"] == {"manifest": len(manifest["papers"]), "evaluated": 0, "excluded": len(manifest["papers"])}
    assert all(item["reason"] == "licence not verified" for item in report["excluded"]) and "concepts" not in report  # no metrics without ground truth
    assert "No paper is evaluable yet" in bm.render_benchmark(report)


def test_manifest_validation_names_every_problem():
    good = json.loads(bm.DEFAULT_MANIFEST.read_text())
    bad = copy.deepcopy(good)
    bad["papers"][1]["id"] = bad["papers"][0]["id"]
    bad["papers"][2]["authors"] = []
    del bad["papers"][3]["title"]
    bad["papers"][4]["license"] = {"status": "verified", "spdx": "Proprietary"}
    bad["papers"][0]["pdf"] = {"path": "../x.pdf", "sha256": "abc"}
    problems = " | ".join(bm.validate_manifest(bad))
    for text in ("duplicate id", "'authors'", "'title'", "a verified licence must be one of", "needs a path and a 64-hex sha256"):
        assert text in problems, text
    assert bm.validate_manifest({"papers": []}) == ["manifest: 'papers' must be a non-empty list"]


def test_annotation_validation_catches_identifiers_fields_duplicates_and_section_references():
    assert bm.validate_annotation(copy.deepcopy(ANNOTATION)) == []
    bad = copy.deepcopy(ANNOTATION)
    bad["concepts"] += [{"name": "Softmax"}, {"name": "Flux Capacitor"}, {"name": "Dropout", "occurrences": {"Results": 1, "Method": 0}}]
    bad["prerequisites"] += [{"concept": "Probability", "covered": True}, {"concept": "Alchemy", "covered": True}, {"concept": "Calculus"}]
    bad["sections"] += [{"title": "1 Method", "role": "instructional"}, {"title": "Odd", "role": "bogus"}]
    del bad["paper_id"]
    problems = " | ".join(bm.validate_annotation(bad))
    for text in ("'paper_id'", "duplicate concept 'Softmax'", "'Flux Capacitor' is not a registry concept", "section 'Results', which is not in 'sections'",
                 "at least 1", "duplicate prerequisite 'Probability'", "'Alchemy' is not a subject", "needs 'covered'", "duplicate section", "role 'bogus'"):
        assert text in problems, text
    approved = copy.deepcopy(ANNOTATION)
    approved["review"] = {"status": "approved"}
    assert any("reviewer's name" in p for p in bm.validate_annotation(approved))


def test_pending_annotations_unverified_licences_and_missing_or_changed_pdfs_never_enter_metrics(tmp_path):
    for kwargs, reason in (({"status": "pending_review"}, "annotation pending_review"), ({"licence": "unverified"}, "licence not verified")):
        report = bm.evaluate_benchmark(_bench(tmp_path / reason.replace(" ", "_"), **kwargs) if (tmp_path / reason.replace(" ", "_")).mkdir() is None else None)
        assert report["counts"]["evaluated"] == 0 and report["excluded"][0]["reason"] == reason and "concepts" not in report
    manifest = _bench(tmp_path / "a") if (tmp_path / "a").mkdir() is None else None
    (manifest.parent / "pdfs" / "numbered-1col.pdf").write_bytes(b"%PDF-changed")
    assert bm.evaluate_benchmark(manifest)["excluded"][0]["reason"] == "PDF does not match its recorded sha256"
    (manifest.parent / "pdfs" / "numbered-1col.pdf").unlink()
    assert bm.evaluate_benchmark(manifest)["excluded"][0]["reason"] == "PDF not available"


def test_approval_needs_a_named_reviewer_and_a_valid_annotation(tmp_path):
    path = tmp_path / "a.json"
    path.write_text(json.dumps(ANNOTATION))
    with pytest.raises(bm.BenchmarkError):
        bm.approve(path, "  ")
    assert json.loads(path.read_text())["review"]["status"] == "pending_review"
    broken = copy.deepcopy(ANNOTATION)
    broken["concepts"].append({"name": "Flux Capacitor"})
    path.write_text(json.dumps(broken))
    with pytest.raises(bm.BenchmarkError):
        bm.approve(path, "Reviewer")
    assert json.loads(path.read_text())["review"]["status"] == "pending_review"  # a refused approval changes nothing
    path.write_text(json.dumps(ANNOTATION))
    assert bm.approve(path, "Reviewer", "2026-11-16")["review"] == {"status": "approved", "reviewer": "Reviewer", "reviewed_on": "2026-11-16"}


def test_a_reviewed_annotation_runs_through_the_full_pdf_pipeline_with_traceable_errors(tmp_path):
    manifest = _bench(tmp_path)
    report = bm.evaluate_benchmark(manifest)
    assert report["counts"]["evaluated"] == 1 and report["excluded"] == [] and report["real_papers"] is True
    row = report["papers"][0]
    assert row["ok"] and row["concepts"]["f1"] == 1.0 and row["occurrences"]["exact"] == 1
    assert row["headings"]["missed"] == ["experiments on cifar-10"]  # the known heading defect, named
    assert row["coverage"]["spurious"] == ["Probability"] and row["coverage"]["missed"] == []  # a false positive, named
    assert row["roles"]["total"] == 7 and report["roles"]["total"] == 7
    text = bm.render_benchmark(report)
    assert "REAL-PAPER BENCHMARK" in text and "false positives: ['Probability']" in text and "AGGREGATE" in text


def test_metric_calculations_on_a_scored_paper():
    from types import SimpleNamespace as N

    paper = N(sections=[N(title="2 Background"), N(title="3 Method"), N(title="Front Matter")], paragraphs=[],
              concepts=[N(name="Softmax"), N(name="Dropout")], missing_prerequisites=[N(concept="Probability", satisfied=True)])
    annotation = {"sections": [{"title": "Background", "role": "instructional"}, {"title": "Experiments", "role": "other"}],
                  "concepts": [{"name": "Softmax"}, {"name": "Transformer"}], "prerequisites": [{"concept": "Probability", "covered": False}]}
    result = bm.score_paper(annotation, paper)
    assert (result["headings"]["tp"], result["headings"]["fp"], result["headings"]["fn"]) == (1, 1, 1)
    assert (result["concepts"]["precision"], result["concepts"]["recall"]) == (0.5, 0.5)
    assert result["concepts"]["missed"] == ["Transformer"] and result["concepts"]["spurious"] == ["Dropout"]
    assert result["coverage"]["precision"] == 0.0 and result["coverage"]["spurious"] == ["Probability"]


def test_results_are_deterministic_and_the_synthetic_evaluation_is_unchanged(tmp_path):
    manifest = _bench(tmp_path)
    assert bm.evaluate_benchmark(manifest) == bm.evaluate_benchmark(manifest)
    assert evaluate()["concepts"]["f1"] > 0
    from backend.prereqai_eval import pdf_eval

    assert pdf_eval.evaluate_pdf()["synthetic"] is True and "real_papers" not in pdf_eval.evaluate_pdf()


def test_the_command_line(tmp_path, capsys):
    assert cli.main(["--benchmark"]) == 0 and "No paper is evaluable yet" in capsys.readouterr().out
    manifest = _bench(tmp_path)
    assert cli.main(["--benchmark", "--manifest", str(manifest), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["counts"]["evaluated"] == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert cli.main(["--benchmark", "--manifest", str(bad)]) == 2 and "prereqai-benchmark-manifest" in capsys.readouterr().err
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps(ANNOTATION))
    assert cli.main(["--approve", str(pending), "--reviewer", "Reviewer"]) == 0 and "approved by Reviewer" in capsys.readouterr().out
    assert json.loads(pending.read_text())["review"]["reviewer"] == "Reviewer"
    assert cli.main(["--approve", str(pending), "--reviewer", " "]) == 2
