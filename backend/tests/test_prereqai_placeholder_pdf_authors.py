import pymupdf
import pytest

from backend.ingestion.document_metadata_extractor import DocumentMetadataExtractor


def _author(tmp_path, embedded):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), "Denoising Diffusion Probabilistic Models", fontsize=20)
    page.insert_text((50, 100), "Jane Roe, John Smith", fontsize=10)
    doc.set_metadata({"title": "Embedded Title", "author": embedded})
    path = tmp_path / "p.pdf"
    doc.save(path)
    return DocumentMetadataExtractor().extract(str(path)).author


@pytest.mark.parametrize("placeholder", ["Administrator", "admin", "Unknown", "user", "Anonymous", "OWNER"])
def test_placeholder_metadata_authors_fall_back_to_the_first_page(tmp_path, placeholder):
    assert _author(tmp_path, placeholder) == "Jane Roe, John Smith"


@pytest.mark.parametrize("real", ["Ashish Vaswani", "Administrator Zhang", "A. Userovich"])
def test_real_embedded_authors_still_win(tmp_path, real):
    assert _author(tmp_path, real) == real
