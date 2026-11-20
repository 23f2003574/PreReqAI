"""Headings on real papers: a section number set apart from its title, numbered lists of names, generic one-word table headers and appendices after the references."""
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.ingestion import PDFIngestionEngine
from backend.parsing.scientific_section_parser import ScientificSectionParser
from backend.prereqai_eval import benchmark

pytestmark = pytest.mark.prereqai
BODY = "We discuss the setting in plain terms and describe each choice made along the way for the reader of this paper. " * 2


def parse(path):
    return ScientificSectionParser().parse(PDFIngestionEngine().ingest(str(path)))


def write(path):
    pdf = canvas.Canvas(str(path), pagesize=A4)

    def line(text, y, x=72, font="Helvetica", size=10):
        pdf.setFont(font, size)
        pdf.drawString(x, y, text)

    line("A Paper About Preference Learning", 790, font="Helvetica-Bold", size=18)
    line("Abstract", 750, font="Helvetica-Bold", size=13)
    line(BODY[:95], 730)
    line("1", 690, font="Helvetica-Bold", size=13); line("Introduction", 690, x=90, font="Helvetica-Bold", size=13)  # number and title are two lines of one block
    line(BODY[:95], 670)
    line("4", 620, font="Helvetica-Bold", size=13); line("Direct Preference Optimization", 620, x=90, font="Helvetica-Bold", size=13)
    line(BODY[:95], 600)
    line("Model", 560, font="Helvetica")  # the header of a table, set like body text
    line("0.7  0.8  0.9", 545)
    line("Author Contributions", 500, font="Helvetica-Bold", size=13)
    for number, name in enumerate(["Gordon Chi", "Virginia Adams", "Max Du", "Kaili Huang", "Ben Prystawski"], 1):
        line(f"{number}. {name}", 500 - 14 * number)
    line("References", 380, font="Helvetica-Bold", size=13)
    line("[1] A. Author. A cited paper. 2017.", 360)
    line("A", 330, font="Helvetica-Bold", size=13); line("Mathematical Derivations", 330, x=90, font="Helvetica-Bold", size=13)
    line(BODY[:95], 310)
    pdf.save()


def test_a_number_set_apart_from_its_title_gives_one_numbered_heading(tmp_path):
    write(tmp_path / "a.pdf")
    titles = [section.title for section in parse(tmp_path / "a.pdf").sections]
    assert "1 Introduction" in titles and "4 Direct Preference Optimization" in titles


def test_contributor_lists_and_generic_table_headers_are_not_sections(tmp_path):
    write(tmp_path / "b.pdf")
    titles = [section.title for section in parse(tmp_path / "b.pdf").sections]
    assert not any(name in " ".join(titles) for name in ("Gordon Chi", "Virginia Adams", "Max Du", "Ben Prystawski")) and "Model" not in titles
    assert "Author Contributions" in titles  # the real heading stays


def test_a_lettered_appendix_after_the_references_is_a_section(tmp_path):
    write(tmp_path / "c.pdf")
    titles = [section.title for section in parse(tmp_path / "c.pdf").sections]
    assert "A Mathematical Derivations" in titles and titles.index("A Mathematical Derivations") > titles.index("References")


def test_a_real_numbered_list_of_steps_with_text_between_items_is_kept(tmp_path):
    pdf = canvas.Canvas(str(tmp_path / "d.pdf"), pagesize=A4)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(72, 780, "Abstract"); pdf.drawString(72, 760, BODY[:95])
    for i, (y, title) in enumerate([(700, "Data Collection"), (620, "Model Training"), (540, "Error Analysis")], 1):
        pdf.drawString(72, y, f"{i}. {title}")
        pdf.drawString(72, y - 20, BODY[:95]); pdf.drawString(72, y - 34, BODY[:95]); pdf.drawString(72, y - 48, BODY[:95])
    pdf.save()
    titles = [s.title for s in parse(tmp_path / "d.pdf").sections]
    assert {"1. Data Collection", "2. Model Training", "3. Error Analysis"} <= set(titles)  # items followed by text are sections, not a name list


def test_heading_depth_tells_sections_from_sub_sections():
    assert [benchmark.heading_depth(t) for t in ("Introduction", "5 Theory", "A Proofs", "5.2 Instability", "A.4 Gradient", "5.2.1 More")] == [1, 1, 1, 2, 2, 3]


def test_real_paper_headings_reach_the_target_and_no_contributor_is_a_heading():
    report = benchmark.evaluate_benchmark()
    assert report["headings"]["f1"] >= 0.70  # was 0.44 before numbered headings were read as one line
    dpo = next(row for row in report["papers"] if row["id"] == "dpo")
    assert not [name for name in dpo["headings"]["spurious"] if name in ("gordon chi", "virginia adams", "zhengxuan wu", "tyler lum")]
    assert "direct preference optimization" not in dpo["headings"]["missed"] and dpo["headings"]["f1"] >= 0.8
