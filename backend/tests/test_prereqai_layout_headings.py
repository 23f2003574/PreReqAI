"""Headings recognised from typography, page provenance of paragraphs, and sessions saved before page numbers existed."""
import json

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.ingestion import PDFIngestionEngine
from backend.parsing.paragraph_segmenter import ParagraphSegmenter
from backend.parsing.scientific_section_parser import ScientificSectionParser
from backend.session import session_codec
from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai

BODY = "We discuss the setting in plain terms and describe each choice made along the way for the reader. " * 3
# Unnumbered headings in wording no pattern list contains.
HEADINGS = ["Why Gradients Vanish", "A Closer Look At Depth", "Stability Matters Most"]


def write_pdf(path, body_bold_lead=False, typography=True):
    pdf = canvas.Canvas(str(path), pagesize=A4)

    def line(text, y, font="Helvetica", size=10):
        pdf.setFont(font, size)
        pdf.drawString(72, y, text)

    line("Learning Deep Networks Well", 780, "Helvetica-Bold", 20)
    line("Ada Lovelace, Alan Turing", 755, "Helvetica-Bold", 14)  # author line: must not become a section
    line("Abstract", 720, "Helvetica-Bold", 14)
    line(BODY[:90], 702)
    y = 670
    for page, heading in enumerate(HEADINGS, start=1):
        if page > 1:
            pdf.showPage()
            y = 780
        line(heading, y, "Helvetica-Bold" if typography else "Helvetica", 14 if typography else 10)
        line(BODY[:95], y - 20)
        line(BODY[:95], y - 34)
        if body_bold_lead and page == 1:  # a bold run inside an ordinary line
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(72, y - 60, "Remark")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(120, y - 60, "that every layer matters for the result described above in plain words.")
        line("Figure 1 Training loss over time", y - 90, "Helvetica-Bold", 14)  # caption: not a heading
    pdf.save()


def parse(path):
    paper = ScientificSectionParser().parse(PDFIngestionEngine().ingest(str(path)))
    return ParagraphSegmenter().segment(paper)


def test_unnumbered_headings_are_found_by_typography_and_the_author_line_and_caption_are_not(tmp_path):
    write_pdf(tmp_path / "a.pdf")
    paper = parse(tmp_path / "a.pdf")
    titles = [section.title for section in paper.sections]
    assert all(heading in titles for heading in HEADINGS)
    assert "Ada Lovelace, Alan Turing" not in titles and "Learning Deep Networks Well" not in titles
    assert not any(title.startswith("Figure") for title in titles)
    assert {s.title: s.heading_source for s in paper.sections}["Why Gradients Vanish"] == "layout"
    assert {s.title: s.heading_source for s in paper.sections}["Abstract"] == "text"


def test_the_same_wording_without_typography_is_not_promoted(tmp_path):
    write_pdf(tmp_path / "plain.pdf", typography=False)  # improved recognition comes from typography, not from wording
    titles = [section.title for section in parse(tmp_path / "plain.pdf").sections]
    assert not any(heading in titles for heading in HEADINGS)


def test_bold_text_inside_an_ordinary_line_is_not_a_heading(tmp_path):
    write_pdf(tmp_path / "b.pdf", body_bold_lead=True)
    titles = [section.title for section in parse(tmp_path / "b.pdf").sections]
    assert "Remark" not in titles and not any(t.startswith("Remark") for t in titles)


def test_page_numbers_reach_sections_and_paragraphs(tmp_path):
    write_pdf(tmp_path / "c.pdf")
    paper = parse(tmp_path / "c.pdf")
    pages = {s.title: s.page_number for s in paper.sections}
    assert [pages[h] for h in HEADINGS] == [1, 2, 3]
    for paragraph in paper.paragraphs:
        assert paragraph.page_number is not None
        assert " ".join(paragraph.content.split())[:40] in " ".join(paper.pages[paragraph.page_number - 1].text.split())
    assert all(page.layout == [] for page in paper.pages)  # typography is not kept in the paper


def test_the_page_numbers_survive_saving_and_loading(tmp_path):
    write_pdf(tmp_path / "d.pdf")
    paper = parse(tmp_path / "d.pdf")
    again = session_codec.decode(json.loads(session_codec.dumps(paper, SessionManager.SCHEMA_VERSION))["session"])
    assert [(p.paragraph_id, p.page_number) for p in again.paragraphs] == [(p.paragraph_id, p.page_number) for p in paper.paragraphs]
    assert [(s.title, s.page_number, s.heading_source) for s in again.sections] == [(s.title, s.page_number, s.heading_source) for s in paper.sections]


def test_a_session_saved_before_page_numbers_loads_with_unknown_pages(tmp_path, monkeypatch):
    from backend.platform import platform
    from backend.session import session_manager

    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    sid = platform.analyze("examples/prerequisites/sample-paper.pdf")["session_id"]
    path = tmp_path / f"{sid}.session"
    saved = json.loads(path.read_bytes())
    assert saved["schema_version"] == SessionManager.SCHEMA_VERSION == 5
    assert any(item["f"]["page_number"] for item in saved["session"]["f"]["paper"]["f"]["paragraphs"])  # provenance is saved
    for item in [*saved["session"]["f"]["paper"]["f"]["paragraphs"], *saved["session"]["f"]["paper"]["f"]["sections"]]:
        for name in ("page_number", "heading_source"):
            item["f"].pop(name, None)  # exactly what a version-4 file holds
    saved["schema_version"] = 4
    path.write_text(json.dumps(saved), encoding="utf-8")
    session_manager.sessions.clear()
    old = session_manager.get(sid)
    assert old is not None and old.schema_version == 5
    assert all(p.page_number is None for p in old.paper.paragraphs) and all(s.heading_source == "text" for s in old.paper.sections)
    session_manager.sessions.clear()
