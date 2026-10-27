"""The reference extractor finds the bibliography under every title the section parser accepts for it (numbered, roman, all caps)."""
from types import SimpleNamespace

import pytest

from backend.parsing.reference_extractor import ReferenceExtractor
from backend.parsing.scientific_section_parser import ScientificSectionParser


def _references(heading):
    text = f"Title\nIntroduction\nbody\n{heading}\n[1] A. Author. A paper. 2020.\n[2] B. Author. Another. 2021.\n"
    paper = ScientificSectionParser().parse(SimpleNamespace(full_text=text, source_path="p", metadata=None, pages=[]))
    paper.references = []
    return ReferenceExtractor().extract(paper).references


@pytest.mark.parametrize("heading", ["References", "REFERENCES", "7 References", "7. REFERENCES", "VII. REFERENCES", "Bibliography", "Works Cited"])
def test_every_bibliography_heading_the_parser_accepts_yields_its_references(heading):
    assert [r.reference_number for r in _references(heading)] == [1, 2]


def test_other_sections_are_not_mistaken_for_the_bibliography():
    text = "Title\nIntroduction\n[1] cited inline\nRelated Work\n[2] another\n"
    paper = ScientificSectionParser().parse(SimpleNamespace(full_text=text, source_path="p", metadata=None, pages=[]))
    paper.references = []
    assert ReferenceExtractor().extract(paper).references == []
