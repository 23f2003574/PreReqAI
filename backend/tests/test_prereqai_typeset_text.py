"""Typeset PDFs: ligature glyphs and typographic dashes inside concept names must not hide the concept."""
import glob
import json

import pymupdf
import pytest

from backend.cli import main
from backend.ingestion.pdf_ingestion_engine import PDFIngestionEngine, clean_pdf_text

FONT = next(iter(glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)), None)
needs_font = pytest.mark.skipif(FONT is None, reason="no TrueType font with ligature glyphs installed")


def _pdf(tmp_path, text):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_font(fontname="dj", fontfile=FONT)
    page.insert_text((72, 72), text, fontsize=10, fontname="dj")
    doc.save(path)
    return path


@needs_font
def test_ligatures_and_typographic_dashes_do_not_hide_concepts(tmp_path, capsys):
    path = _pdf(tmp_path, "Abstract\nA Diﬀusion Model with Q‑learning and an Actor–Critic.\n")
    assert "ﬀ" in pymupdf.open(path)[0].get_text()  # the PDF really holds the ligature glyph
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    concepts = json.loads(capsys.readouterr().out)["report"]["concepts"]
    assert {"Diffusion Model", "Q-Learning", "Actor-Critic"} <= set(concepts)


@needs_font
def test_ingested_text_is_plain_ascii_for_those_glyphs(tmp_path):
    path = _pdf(tmp_path, "The ﬁrst eﬃcient ﬂow, Feed­forward.\n")
    text = PDFIngestionEngine().ingest(str(path)).full_text
    assert "first efficient flow, Feedforward." in text


def test_clean_text_leaves_ordinary_text_and_hyphens_alone():
    plain = "Multi-head attention, 12 layers, x_i = W q (eq. 3).\n"
    assert clean_pdf_text(plain) == plain
    assert clean_pdf_text("pages 1–5") == "pages 1-5"


@needs_font
def test_title_author_and_metadata_use_the_same_cleaned_text_as_the_body(tmp_path, capsys):
    """Ingestion cleans body text; the metadata extractor reads the PDF separately, so it must clean too."""
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_font(fontname="dj", fontfile=FONT)
    page.insert_text((72, 72), "Eﬃcient Diﬀusion for Q‑learning", fontsize=18, fontname="dj")
    page.insert_text((72, 110), "Jane Smith, Ann Lee", fontsize=11, fontname="dj")
    page.insert_text((72, 140), "Abstract\nA diﬀusion model.\n", fontsize=10, fontname="dj")
    doc.set_metadata({"keywords": "eﬃcient, diﬀusion"})
    doc.save(path)
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]
    assert report["paper"]["title"] == "Efficient Diffusion for Q-learning"
    assert report["paper"]["author"] == "Jane Smith, Ann Lee"
    meta = PDFIngestionEngine().ingest(str(path)).metadata
    assert meta.keywords == "efficient, diffusion"
    assert "Diffusion Model" in report["concepts"]
