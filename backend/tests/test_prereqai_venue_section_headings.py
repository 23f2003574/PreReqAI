"""Headings common in conference papers (NeurIPS funding disclosure, lettered appendices, 'Conclusion and Discussion', a trailing colon)
start their own section, so a bibliography or appendix is not folded into the section before it."""
import pytest

from types import SimpleNamespace

from backend.parsing.scientific_section_parser import SECTION_PATTERN, ScientificSectionParser

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("heading", [
    "Reference", "References:", "Literature Cited", "Acknowledgments and Disclosure of Funding", "Conclusion and Discussion",
    "Discussion and Conclusions", "Limitations and Future Work", "Results and Analysis", "Experiments and Results",
    "Broader Impact Statement", "Appendix A", "Appendix", "Supplementary Materials", "5 Conclusion and Discussion",
])
def test_venue_headings_are_recognised(heading):
    assert SECTION_PATTERN.search(heading)


@pytest.mark.parametrize("line", [
    "The appendix A shows more results",           # a sentence, not a heading
    "Appendix A shows the full proof of Theorem 2.",
    "Results and analysis of the model are shown below",
    "Reference implementations are available online.",
    "Notation.",                                   # a one-word sentence ending in a period stays body text
])
def test_sentences_that_start_like_a_heading_are_not(line):
    assert SECTION_PATTERN.search(line) is None


def test_a_reference_list_after_a_funding_disclosure_and_an_appendix_become_their_own_sections():
    text = ("1 Introduction\nWe study attention.\nConclusion and Discussion\nIt works.\n"
            "Acknowledgments and Disclosure of Funding\nFunded by X.\nReferences:\n[1] Policy gradient methods.\nAppendix A\nMore proofs.\n")
    paper = ScientificSectionParser().parse(SimpleNamespace(source_path="p.pdf", metadata=None, pages=[], full_text=text))
    assert [section.title for section in paper.sections] == [
        "1 Introduction", "Conclusion and Discussion", "Acknowledgments and Disclosure of Funding", "References:", "Appendix A"]
    assert "Policy gradient" in paper.sections[3].content and "Policy gradient" not in paper.sections[2].content
