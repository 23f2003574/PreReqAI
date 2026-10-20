"""IEEE-style headings ("II. PROPOSED METHOD") start their own section instead of folding into the previous one."""
from backend.ingestion import RawDocument
from backend.ingestion.pdf_ingestion_engine import RawPage
from backend.parsing.scientific_section_parser import SECTION_PATTERN, ScientificSectionParser

TEXT = ("ABSTRACT\nWe study x.\nI. INTRODUCTION\nBody one.\nII. PROPOSED METHOD\nBody two.\nA. Network Design\nDetails.\n"
        "III. EXPERIMENTAL EVALUATION\nBody three.\nIV. CONCLUSION\nDone.\nREFERENCES\n[1] A. Paper.\n")


def test_roman_numbered_all_caps_headings_are_sections():
    titles = [m.group().strip() for m in SECTION_PATTERN.finditer(TEXT)]
    assert titles == ["ABSTRACT", "I. INTRODUCTION", "II. PROPOSED METHOD", "III. EXPERIMENTAL EVALUATION", "IV. CONCLUSION", "REFERENCES"]


def test_author_lines_and_sentences_are_not_headings():
    text = "I. Goodfellow and Y. Bengio\nIn II. the other IV. THING continues\nX. A\nII. Proposed method\n"
    assert [m.group() for m in SECTION_PATTERN.finditer(text)] == []


def test_the_section_content_follows_the_new_headings():
    document = RawDocument(source_path="p.pdf", metadata=None, pages=[RawPage(page_number=1, text=TEXT)])
    sections = {s.title: s.content for s in ScientificSectionParser().parse(document).sections}
    assert sections["II. PROPOSED METHOD"] == "Body two.\nA. Network Design\nDetails."
    assert sections["III. EXPERIMENTAL EVALUATION"] == "Body three."
