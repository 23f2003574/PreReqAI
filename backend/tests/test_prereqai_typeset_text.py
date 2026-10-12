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
