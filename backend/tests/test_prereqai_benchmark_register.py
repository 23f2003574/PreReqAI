"""Adding a paper to the real-paper benchmark: PDF hash and licence recorded on a named person's word, annotations stay pending until a person approves them, and the status says what is missing."""
import json
import shutil

import pymupdf
import pytest

from backend.prereqai_eval import benchmark
from backend.prereqai_eval.__main__ import main

pytestmark = pytest.mark.prereqai


@pytest.fixture
def folder(tmp_path):
    target = tmp_path / "benchmark"
    shutil.copytree(benchmark.BENCHMARK_DIR, target)
    return target


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "paper.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), "1 Introduction\n\nThe softmax function normalises scores, and the softmax is used everywhere in the model.", fontsize=11)
    document.save(str(path))
    return path


NEW = {"title": "A Test Paper", "authors": ["A. Writer"], "source_url": "https://example.org/paper", "venue": "TestConf", "year": 2024}


def register(folder, pdf, **overrides):
    arguments = {"paper_id": "test-paper", "licence_spdx": "CC-BY-4.0", "licence_evidence_url": "https://example.org/licence", "licence_checked_by": "A. Reviewer", "metadata": NEW}
    arguments.update(overrides)
    return benchmark.register_paper(folder / "manifest.json", pdf, **arguments)


def test_a_new_paper_gets_its_hash_licence_and_a_pending_annotation_and_is_not_scored(folder, pdf):
    entry = register(folder, pdf)
    assert (folder / "pdfs" / "test-paper.pdf").read_bytes() == pdf.read_bytes()
    assert entry["pdf"]["sha256"] == benchmark._sha256(pdf) and entry["license"]["verified_by"] == "A. Reviewer" and entry["license"]["spdx"] == "CC-BY-4.0"
    annotation = json.loads((folder / "annotations" / "test-paper.json").read_text())
    assert annotation["review"] == {"status": "pending_review"} and annotation["concepts"] == []
    assert benchmark.load_manifest(folder / "manifest.json")  # still a valid manifest
    report = benchmark.evaluate_benchmark(folder / "manifest.json")
    assert "test-paper" not in {r["id"] for r in report["papers"]} and {"id": "test-paper", "title": "A Test Paper", "reason": "annotation pending_review"} in report["excluded"]
    row = next(r for r in benchmark.status(folder / "manifest.json") if r["id"] == "test-paper")
    assert not row["ready"] and len(row["blockers"]) == 1 and "pending_review" in row["blockers"][0]


def test_only_a_persons_approval_makes_it_scored_and_a_changed_pdf_is_caught(folder, pdf):
    register(folder, pdf)
    path = folder / "annotations" / "test-paper.json"
    annotation = json.loads(path.read_text())
    annotation["sections"] = [{"title": "1 Introduction", "role": "instructional"}]
    annotation["concepts"] = [{"name": "Softmax", "occurrences": {"1 Introduction": 2}}]
    path.write_text(json.dumps(annotation))
    scored = lambda: {r["id"] for r in benchmark.evaluate_benchmark(folder / "manifest.json")["papers"]}
    assert "test-paper" not in scored()  # filled in but still unreviewed
    benchmark.approve(path, "A. Reviewer")
    assert "test-paper" in scored()
    assert next(r for r in benchmark.status(folder / "manifest.json") if r["id"] == "test-paper")["ready"]
    (folder / "pdfs" / "test-paper.pdf").write_bytes(pdf.read_bytes() + b"tampered")
    assert "test-paper" not in scored()
    assert "sha256" in next(r for r in benchmark.status(folder / "manifest.json") if r["id"] == "test-paper")["blockers"][0]


def test_an_existing_unverified_entry_is_filled_in_and_a_worked_annotation_is_kept(folder, pdf):
    path = folder / "annotations" / "adam.json"
    worked = json.loads(path.read_text())
    worked["concepts"] = [{"name": "Adam Optimizer", "occurrences": {"Abstract": 1}}]
    path.write_text(json.dumps(worked))
    entry = register(folder, pdf, paper_id="adam", metadata=None)
    assert entry["title"] and entry["license"]["status"] == "verified" and json.loads(path.read_text())["concepts"] == worked["concepts"]
    assert len(benchmark.load_manifest(folder / "manifest.json")["papers"]) == 8


@pytest.mark.parametrize("overrides,message", [
    ({"licence_spdx": "All-Rights-Reserved"}, "licence must be one of"),
    ({"licence_checked_by": " "}, "person who checked the licence"),
    ({"licence_evidence_url": ""}, "licence evidence link"),
    ({"paper_id": "Bad Id"}, "id must be"),
    ({"metadata": None}, "a new paper needs"),
])
def test_a_registration_without_a_real_licence_check_or_valid_data_changes_nothing(folder, pdf, overrides, message):
    before = (folder / "manifest.json").read_text()
    with pytest.raises(benchmark.BenchmarkError) as error:
        register(folder, pdf, **overrides)
    assert message in " ".join(error.value.problems) and (folder / "manifest.json").read_text() == before and not list((folder / "pdfs").glob("*other*")) and not (folder / "pdfs" / "test-paper.pdf").exists()


def test_a_non_pdf_and_an_already_verified_paper_are_refused(folder, pdf, tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_text("not a pdf")
    with pytest.raises(benchmark.BenchmarkError, match="not a PDF"):
        register(folder, fake)
    register(folder, pdf)
    with pytest.raises(benchmark.BenchmarkError, match="already has a verified licence"):
        register(folder, pdf)


def test_the_command_line_registers_and_reports_the_status(folder, pdf, capsys):
    manifest = str(folder / "manifest.json")
    assert main(["--status", "--manifest", manifest]) == 0 and "3 of 8 papers ready" in capsys.readouterr().out
    code = main(["--register", str(pdf), "--manifest", manifest, "--id", "test-paper", "--licence", "CC-BY-4.0", "--licence-evidence", "https://example.org/licence",
                 "--licence-checked-by", "A. Reviewer", "--title", "A Test Paper", "--author", "A. Writer", "--source-url", "https://example.org/p", "--venue", "TestConf", "--year", "2024"])
    assert code == 0 and "pending_review" in capsys.readouterr().out
    assert main(["--register", str(pdf), "--manifest", manifest, "--id", "other"]) == 2 and "licence must be one of" in capsys.readouterr().err
    assert main(["--status", "--manifest", manifest, "--json"]) == 0 and len(json.loads(capsys.readouterr().out)) == 9


# ---- the shipped benchmark data ----

def test_the_shipped_papers_have_verified_licences_matching_hashes_and_reviewed_annotations():
    manifest = benchmark.load_manifest(benchmark.DEFAULT_MANIFEST)
    verified = [p for p in manifest["papers"] if p["license"]["status"] == "verified"]
    assert {p["id"] for p in verified} == {"dpo", "mixtral", "chain-of-thought"}
    for paper in verified:
        licence = paper["license"]
        assert licence["spdx"] == "CC-BY-4.0" and licence["evidence_url"].startswith("https://arxiv.org/abs/") and licence["verified_by"] and licence["verified_on"]
        pdf = benchmark.BENCHMARK_DIR / paper["pdf"]["path"]
        assert pdf.read_bytes().startswith(b"%PDF-") and benchmark._sha256(pdf) == paper["pdf"]["sha256"]
        annotation = json.loads((benchmark.BENCHMARK_DIR / paper["annotation"]).read_text())
        assert annotation["review"]["status"] == "approved" and annotation["review"]["reviewer"] and "not by a human reader" in annotation["review_note"]  # who approved, and what that is worth, is on record
        assert annotation["sections"] and annotation["concepts"] and annotation["prerequisites"] == [] and benchmark.validate_annotation(annotation) == []
    unverified = [p for p in manifest["papers"] if p["license"]["status"] != "verified"]
    assert unverified and all("non-exclusive distribution licence" in p["license"]["note"] for p in unverified)


def test_the_shipped_benchmark_scores_three_papers_and_names_the_errors_and_leaves_coverage_unscored():
    report = benchmark.evaluate_benchmark()
    assert report["counts"]["evaluated"] == 3 and all(row["ok"] and row["coverage"] is None for row in report["papers"]) and report["coverage"] is None
    assert {"precision", "recall", "f1", "tp", "fp", "fn"} <= set(report["headings"]) and {"precision", "recall", "f1"} <= set(report["concepts"])
    dpo = next(row for row in report["papers"] if row["id"] == "dpo")
    assert "Convolutional Neural Network" not in dpo["concepts"]["spurious"]  # the 'CNN' of CNN/DailyMail used to be a named false positive
    assert "direct preference optimization" not in dpo["headings"]["missed"]  # a numbered heading that used to be missed (its number was a line of its own)
    text = benchmark.render_benchmark(report)
    assert "false positives" in text and "false negatives" in text and "coverage not annotated" in text


def test_a_pending_annotation_is_never_scored(folder):
    path = folder / "annotations" / "mixtral.json"
    data = json.loads(path.read_text())
    data["review"] = {"status": "pending_review"}
    path.write_text(json.dumps(data))
    report = benchmark.evaluate_benchmark(folder / "manifest.json")
    assert "mixtral" not in {r["id"] for r in report["papers"]} and {"id": "mixtral", "title": report["excluded"][-1]["title"], "reason": "annotation pending_review"} in report["excluded"] or \
        any(e["id"] == "mixtral" and e["reason"] == "annotation pending_review" for e in report["excluded"])
    assert report["counts"]["evaluated"] == 2


def test_an_approved_annotation_without_prerequisites_reports_coverage_as_not_annotated(folder):
    report = benchmark.evaluate_benchmark(folder / "manifest.json")
    row = next(r for r in report["papers"] if r["id"] == "mixtral")
    assert row["ok"] and row["coverage"] is None and report["coverage"] is None
    text = benchmark.render_benchmark(report)
    assert "coverage not annotated" in text and "not annotated for any evaluated paper" in text
