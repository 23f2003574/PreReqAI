"""A title wrapped over several lines is read whole; uniform text and a single-line title keep the old behaviour."""
import pymupdf

from backend.ingestion.document_metadata_extractor import DocumentMetadataExtractor


def _title(tmp_path, lines):
    path = tmp_path / "p.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    y = 90
    for text, size in lines:
        page.insert_text((72, y), text, fontsize=size)
        y += size + 8
    doc.save(path)
    return DocumentMetadataExtractor().extract(str(path)).title


def test_two_line_title_is_joined(tmp_path):
    lines = [("Denoising Diffusion Probabilistic", 20), ("Models for Image Synthesis", 20), ("Jonathan Ho, Ajay Jain", 11), ("Abstract", 10)]
    assert _title(tmp_path, lines) == "Denoising Diffusion Probabilistic Models for Image Synthesis"


def test_single_line_title_does_not_absorb_the_author_line(tmp_path):
    lines = [("Attention Is All You Need", 20), ("Ashish Vaswani, Noam Shazeer", 11), ("Abstract", 10)]
    assert _title(tmp_path, lines) == "Attention Is All You Need"


def test_text_in_one_font_size_still_uses_only_the_first_line(tmp_path):
    lines = [("First line", 10), ("Second line", 10), ("Third line", 10)]
    assert _title(tmp_path, lines) == "First line"
