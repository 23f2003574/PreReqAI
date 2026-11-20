"""Table column headers, captions and bullet lists are not section headings; headings set apart in the layout are found even when the text layer drops their number."""
from collections import Counter

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.ingestion import PDFIngestionEngine
from backend.parsing.scientific_section_parser import ScientificSectionParser

pytestmark = pytest.mark.prereqai
BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=12)
HEAD = ParagraphStyle("head", fontName="Times-Bold", fontSize=12, leading=15, spaceBefore=10, spaceAfter=4)
CELL = ParagraphStyle("cell", fontName="Times-Bold", fontSize=10, leading=12)
TEXT = "We study how experts are chosen by a router and how the learned weights behave across many tasks and several model sizes. " * 3


def _paper(tmp_path, tables=2):
    story = [Paragraph("Abstract", HEAD), Paragraph(TEXT, BODY), Paragraph("1 Introduction", HEAD), Paragraph(TEXT, BODY),
             Paragraph("2 Method", HEAD), Paragraph(TEXT, BODY), Paragraph("3 Results", HEAD), Paragraph(TEXT, BODY)]
    for number in range(1, tables + 1):
        story += [Paragraph(f"Table {number}: Results on the benchmark for each model.", BODY), Spacer(1, 4),
                  Table([[Paragraph(h, CELL) for h in ("Model", "Dataset", "Results", "Approach")], ["A 7B", "GSM8K", "55.1", "ours"], ["B 13B", "MATH", "40.2", "base"],
                         ["C 70B", "GSM8K", "61.0", "ours"]], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0))])), Spacer(1, 8),
                  Paragraph(TEXT, BODY)]
    story += [Paragraph("4 Routing analysis", HEAD), Paragraph(TEXT, BODY), Paragraph("5 Conclusion", HEAD), Paragraph(TEXT, BODY)]
    path = tmp_path / "paper.pdf"
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return path


def _titles(path):
    return [section.title for section in ScientificSectionParser().parse(PDFIngestionEngine().ingest(str(path))).sections]


def test_table_headers_and_captions_are_not_headings(tmp_path):
    titles = _titles(_paper(tmp_path))
    assert not {"Model", "Dataset", "Approach"} & set(titles) and not any(t.lower().startswith("table") for t in titles), titles
    assert "4 Routing analysis" in titles and "3 Results" in titles and "2 Method" in titles, titles


def test_no_title_repeats_more_than_twice(tmp_path):
    titles = _titles(_paper(tmp_path, tables=4))
    assert max(Counter(titles).values()) <= 2 and titles.count("Results") == 0, titles


def test_the_benchmark_papers_have_no_repeated_or_generic_spurious_headings():
    from backend.pipeline import ResearchPaperPipeline

    for paper_id in ("dpo", "mixtral", "chain-of-thought"):
        titles = [s.title for s in ResearchPaperPipeline().run(f"backend/prereqai_eval/benchmark/pdfs/{paper_id}.pdf").paper.sections]
        assert max(Counter(titles).values()) <= 2, (paper_id, Counter(titles).most_common(3))
        assert not {"Model", "Dataset", "Approach", "Ablations"} & set(titles), (paper_id, titles)


def test_a_heading_whose_number_the_text_layer_lost_is_found_with_its_number():
    from backend.pipeline import ResearchPaperPipeline

    mixtral = [s.title for s in ResearchPaperPipeline().run("backend/prereqai_eval/benchmark/pdfs/mixtral.pdf").paper.sections]
    chain = [s.title for s in ResearchPaperPipeline().run("backend/prereqai_eval/benchmark/pdfs/chain-of-thought.pdf").paper.sections]
    assert "5 Routing analysis" in mixtral and "5 Symbolic Reasoning" in chain and "3.2 Results" in chain
