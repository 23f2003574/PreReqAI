import pymupdf
import pytest

from backend.ingestion import RawDocument
from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.pipeline.research_paper_pipeline import ResearchPaperPipeline

pytestmark = pytest.mark.prereqai


def _pdf(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Attention uses softmax.")
    path = tmp_path / "p.pdf"
    doc.save(path)
    return str(path)


def test_a_document_without_pages_is_rejected_at_the_ingestion_boundary(tmp_path):
    pipeline = ResearchPaperPipeline()
    pipeline.ingestion.ingest = lambda path: RawDocument(path, DocumentMetadata("t", "a", "", "", "", "", 0), [])
    with pytest.raises(ValueError, match="no pages") as caught:
        pipeline.run(_pdf(tmp_path))
    assert caught.value.failed_stage == "ingestion"


def test_a_normal_document_continues_through_the_pipeline(tmp_path):
    result = ResearchPaperPipeline().run(_pdf(tmp_path))
    assert {c.name for c in result.paper.concepts} >= {"Attention", "Softmax"}
