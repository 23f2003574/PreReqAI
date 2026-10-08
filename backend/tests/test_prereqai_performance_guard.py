"""A coarse guard against major performance regressions in the analysis
workflow, read from the workflow's own per-stage timings. On a 12-page paper the
two costly stages are table_extractor (pdfplumber table detection, ~97% of a
run) and ingestion (PDF text extraction); every other stage is sub-millisecond.
Budgets are ~10-20x what they measure on a development machine, so only a real
regression (e.g. a stage reprocessing the whole document per page) trips them;
PREREQAI_PERF_FACTOR scales them for slow CI machines. The guard only reads the
result, so it cannot change it."""
import os
from statistics import median

import pymupdf as fitz
import pytest

import backend.ingestion.document_metadata_extractor as metadata_module
import backend.ingestion.pdf_ingestion_engine as ingestion_module
from backend.platform import PreReqAIPlatform

PAGES = 12
FACTOR = float(os.environ.get("PREREQAI_PERF_FACTOR", "1"))
# Seconds per page for the costly stages, and for the whole run.
BUDGET_PER_PAGE = {"table_extractor": 0.5, "ingestion": 0.1}
TOTAL_PER_PAGE = 0.75
BODY = "We use softmax, attention, convolution, gradient descent, backpropagation and linear algebra. " * 8


@pytest.fixture(scope="module")
def paper(tmp_path_factory):
    document = fitz.open()
    for index in range(PAGES):
        heading = "Attention Is All You Need\n\nAbstract\n" if index == 0 else ""
        document.new_page().insert_textbox(fitz.Rect(50, 50, 550, 800), f"{heading}{index + 1} Section\n{BODY}\n$x = W y + b$ (1)\n", fontsize=9)
    path = tmp_path_factory.mktemp("perf") / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _median_timings(paper, runs=3):
    platform = PreReqAIPlatform()
    outcomes = [platform.analyze(paper) for _ in range(runs)]
    assert all(outcome["status"] == "success" for outcome in outcomes)
    return {stage: median(outcome["timings"][stage] for outcome in outcomes) for stage in outcomes[0]["timings"]}, outcomes


def test_the_costly_stages_stay_within_a_generous_per_page_budget(paper):
    timings, _ = _median_timings(paper)

    for stage, per_page in BUDGET_PER_PAGE.items():
        assert timings[stage] <= per_page * PAGES * FACTOR, f"{stage} took {timings[stage]:.2f}s for {PAGES} pages"
    assert sum(timings.values()) <= TOTAL_PER_PAGE * PAGES * FACTOR


def test_no_other_stage_becomes_a_major_cost(paper):
    timings, _ = _median_timings(paper)

    others = {stage: seconds for stage, seconds in timings.items() if stage not in BUDGET_PER_PAGE}
    assert sum(others.values()) <= 0.05 * PAGES * FACTOR, sorted(others.items(), key=lambda item: -item[1])[:3]


def test_ingestion_parses_the_pdf_once(paper, monkeypatch):
    opened = []
    real_open = fitz.open
    counting = lambda *args, **kwargs: opened.append(args) or real_open(*args, **kwargs)
    monkeypatch.setattr(ingestion_module.fitz, "open", counting)
    monkeypatch.setattr(metadata_module.fitz, "open", counting)

    document = ingestion_module.PDFIngestionEngine().ingest(paper)

    assert len(opened) == 1  # metadata and page text come from the same open document
    assert document.metadata.page_count == PAGES and len(document.pages) == PAGES


def test_metadata_is_the_same_from_a_path_or_an_open_document(paper):
    extractor = metadata_module.DocumentMetadataExtractor()

    with fitz.open(paper) as pdf:
        assert extractor.extract_from(pdf) == extractor.extract(paper)


def test_the_guard_does_not_alter_the_workflow_result(paper):
    _, guarded = _median_timings(paper)
    plain = PreReqAIPlatform().analyze(paper)

    for outcome in guarded:
        assert outcome["report"] == plain["report"] and list(outcome["timings"]) == list(plain["timings"])
