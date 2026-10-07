"""FigureExtractor closes the PDF it opens even when decoding an image fails,
so a failed analysis never leaks the document handle (which on Windows also
keeps the uploaded temp file locked)."""
import pymupdf
import pytest

from backend.parsing import figure_extractor as module
from backend.parsing.figure_extractor import FigureExtractor


def _pdf_with_an_image(path):
    document = pymupdf.open()
    page = document.new_page()
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 4, 4), False)
    image.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 144, 144), pixmap=image)
    document.save(path)
    return path


def _tracking_open(monkeypatch):
    opened = []
    real_open = module.fitz.open
    monkeypatch.setattr(module.fitz, "open", lambda *a, **k: opened.append(real_open(*a, **k)) or opened[-1])
    return opened


def test_the_document_is_closed_when_an_image_fails_to_decode(tmp_path, monkeypatch):
    pdf = _pdf_with_an_image(tmp_path / "paper.pdf")
    opened = _tracking_open(monkeypatch)

    def broken_pixmap(*args, **kwargs):
        raise RuntimeError("cannot decode image")

    monkeypatch.setattr(module.fitz, "Pixmap", broken_pixmap)

    with pytest.raises(RuntimeError, match="cannot decode image"):  # the error still propagates unchanged
        FigureExtractor().extract(str(pdf), paper=type("Paper", (), {})())

    assert len(opened) == 1 and opened[0].is_closed


def test_a_successful_extraction_still_reports_figures_and_closes_the_document(tmp_path, monkeypatch):
    pdf = _pdf_with_an_image(tmp_path / "paper.pdf")
    opened = _tracking_open(monkeypatch)

    paper = FigureExtractor().extract(str(pdf), paper=type("Paper", (), {})())

    assert [(f.page_number, f.width, f.height) for f in paper.figures] == [(1, 4, 4)]
    assert opened[0].is_closed
