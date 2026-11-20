"""Paragraphs follow the PDF's layout (blocks, indented lines after short ones), in one- and two-column papers, with their page and section."""
import statistics

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, PageBreak, PageTemplate, Paragraph, SimpleDocTemplate, Spacer

from backend.pipeline import ResearchPaperPipeline

pytestmark = pytest.mark.prereqai
BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=12, firstLineIndent=14, alignment=4)
FLUSH = ParagraphStyle("flush", parent=BODY, firstLineIndent=0, spaceBefore=8)
HEAD = ParagraphStyle("head", fontName="Times-Bold", fontSize=12, leading=15, spaceBefore=10, spaceAfter=4)
SENTENCE = "The router assigns every token to two experts and the weights of both are combined after a softmax over the scores. "


def _prose(n, tag):
    return (f"Paragraph {tag}. " + SENTENCE * n).strip()


def _story(indent_only=False):
    style = BODY if indent_only else FLUSH
    story = []
    for number, title in enumerate(["Abstract", "1 Introduction", "2 Method", "3 Results"]):
        story.append(Paragraph(title, HEAD))
        story += [Paragraph(_prose(3 + k, f"{title[:3]}{k}"), style) for k in range(5)]
    return story


def _build(path, two_column=False, indent_only=False):
    if two_column:
        document = BaseDocTemplate(str(path), pagesize=A4)
        width, height = A4
        frames = [Frame(40, 40, (width - 100) / 2, height - 80, id="left"), Frame(60 + (width - 100) / 2, 40, (width - 100) / 2, height - 80, id="right")]
        document.addPageTemplates([PageTemplate(id="two", frames=frames)])
        document.build(_story(indent_only))
    else:
        SimpleDocTemplate(str(path), pagesize=A4).build(_story(indent_only))
    return ResearchPaperPipeline().run(str(path)).paper


@pytest.mark.parametrize("two_column", [False, True])
@pytest.mark.parametrize("indent_only", [False, True])
def test_paragraphs_are_cut_at_the_layouts_paragraph_breaks(tmp_path, two_column, indent_only):
    paper = _build(tmp_path / "p.pdf", two_column, indent_only)
    sizes = [len(p.content) for p in paper.paragraphs if p.section_title in ("1 Introduction", "2 Method")]
    assert len(sizes) >= 10, sizes  # the five paragraphs of each of the two sections, not one block per section
    assert statistics.median([len(p.content) for p in paper.paragraphs]) < 900 and max(len(p.content) for p in paper.paragraphs) <= 2500
    assert not any(p.content.startswith("Paragraph") and "Paragraph " in p.content[10:] for p in paper.paragraphs)  # no two paragraphs run together


def test_every_paragraph_keeps_its_section_and_its_page(tmp_path):
    paper = _build(tmp_path / "p.pdf", two_column=False)
    pages = {page.page_number: " ".join(page.text.split()) for page in paper.pages}
    sections = {s.title for s in paper.sections}
    for paragraph in paper.paragraphs:
        assert paragraph.section_title in sections and paragraph.page_number in pages
        assert " ".join(paragraph.content.split())[:60] in pages[paragraph.page_number], paragraph.content[:60]
    assert max(p.page_number for p in paper.paragraphs) > 1  # the story runs over several pages


def test_layout_is_not_kept_in_the_paper_after_segmentation(tmp_path):
    paper = _build(tmp_path / "p.pdf")
    assert all(not page.paragraph_starts and not page.layout for page in paper.pages)


def test_a_long_block_without_layout_is_cut_at_sentence_ends():
    from backend.models import Paper, PaperSection
    from backend.parsing.paragraph_segmenter import MAX_PARAGRAPH, ParagraphSegmenter

    paper = Paper(source_path="x.pdf", metadata=None)
    paper.sections = [PaperSection(title="1 Introduction", content=("A sentence that goes on for a while. " * 200).strip())]
    paragraphs = ParagraphSegmenter().segment(paper).paragraphs
    assert len(paragraphs) >= 3 and all(len(p.content) <= MAX_PARAGRAPH for p in paragraphs) and all(p.content.endswith(".") for p in paragraphs)


def test_the_sample_paper_is_segmented_as_before():
    paper = ResearchPaperPipeline().run("examples/prerequisites/sample-paper.pdf").paper
    assert len(paper.paragraphs) == 5 and {p.page_number for p in paper.paragraphs} == {1}


@pytest.mark.parametrize("name", ["dpo", "mixtral", "chain-of-thought"])
def test_real_papers_have_paragraph_sized_paragraphs(name):
    paper = ResearchPaperPipeline().run(f"backend/prereqai_eval/benchmark/pdfs/{name}.pdf").paper
    sizes = [len(p.content) for p in paper.paragraphs]
    assert statistics.median(sizes) < 900 and max(sizes) <= 2500, (name, statistics.median(sizes), max(sizes))
