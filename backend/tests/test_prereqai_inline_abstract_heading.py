import pytest

from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.ingestion.pdf_ingestion_engine import RawDocument, RawPage
from backend.parsing import ScientificSectionParser


def _sections(text):
    document = RawDocument("p.pdf", DocumentMetadata("t", "a", "", "", "", "", 1), [RawPage(1, text)])
    return [(s.title, s.content) for s in ScientificSectionParser().parse(document).sections]


@pytest.mark.parametrize("separator", ["\u2014", " \u2013 ", ": ", "\u2014 "])
def test_an_inline_abstract_heading_starts_the_abstract_section(separator):
    sections = _sections(f"A Paper\nAbstract{separator}We study attention.\nIt works.\n1 Introduction\nBody.\n")
    assert sections == [("Front Matter", "A Paper"), ("Abstract", "We study attention.\nIt works."), ("1 Introduction", "Body.")]


def test_a_standalone_abstract_heading_is_unchanged():
    assert _sections("A Paper\nAbstract\nWe study attention.\n1 Introduction\nBody.\n") == [
        ("Front Matter", "A Paper"), ("Abstract", "We study attention."), ("1 Introduction", "Body.")]


@pytest.mark.parametrize("line", ["Abstract algebra is a branch of mathematics.", "Abstractions help us reason."])
def test_prose_starting_with_the_word_is_not_a_heading(line):
    assert _sections(f"1 Introduction\n{line}\n") == [("1 Introduction", line)]
