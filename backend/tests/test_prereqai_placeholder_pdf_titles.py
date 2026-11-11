import pymupdf
import pytest

from backend.ingestion.document_metadata_extractor import DocumentMetadataExtractor

FIRST_PAGE_TITLE = "Denoising Diffusion Probabilistic Models"


def _title(tmp_path, embedded):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), FIRST_PAGE_TITLE, fontsize=20)
    page.insert_text((50, 140), "Abstract. We use diffusion models.", fontsize=10)
    doc.set_metadata({"title": embedded})
    path = tmp_path / "p.pdf"
    doc.save(path)
    return DocumentMetadataExtractor().extract(str(path)).title


@pytest.mark.parametrize("placeholder", ["Microsoft Word - paper.docx", "untitled", "Untitled1", "paper.docx", "draft_v2.tex", "microsoft powerpoint - slides.pptx", "Final Draft.docx", "My Paper v2.pdf"])
def test_placeholder_metadata_titles_fall_back_to_the_first_page(tmp_path, placeholder):
    assert _title(tmp_path, placeholder) == FIRST_PAGE_TITLE


@pytest.mark.parametrize("real", ["Embedded Title", "Attention Is All You Need", "Untitled Goose Game Analysis", "Notes on paper.docx formats", "Reading .tex Files in LaTeX"])
def test_real_embedded_titles_still_win(tmp_path, real):
    assert _title(tmp_path, real) == real
