"""More unnumbered headings from published papers start their own section (found by probing common headings: these were missed
and folded into the section before them)."""
from types import SimpleNamespace

import pytest

from backend.parsing.scientific_section_parser import SECTION_PATTERN, ScientificSectionParser

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("heading", [
    "Introduction and Motivation", "Background and Related Work", "Preliminaries and Notation", "Main Results", "Key Results",
    "Qualitative Results", "Hyperparameters", "Evaluation Metrics", "Experimental Setup and Results", "Training Objective",
    "Overview of the Method", "Ethical Considerations", "Societal Impact", "Code Availability", "Data Availability",
    "Author Contributions", "Competing Interests", "Funding", "Limitations and Broader Impact", "Broader Impacts and Limitations",
    "Main Results:", "5 Main Results",
])
def test_further_headings_are_recognised(heading):
    assert SECTION_PATTERN.search(heading)


@pytest.mark.parametrize("line", [
    "Funding was provided by a grant from the foundation.",
    "Main results are shown in Table 2.",
    "Hyperparameters are listed below",
    "The key results of this section follow.",
    "Data availability statements vary by journal.",
    "Summary",                      # still too ambiguous to add
])
def test_sentences_and_ambiguous_words_stay_body_text(line):
    assert SECTION_PATTERN.search(line) is None


def test_a_document_with_these_headings_splits_where_expected():
    text = ("1 Introduction\nWe study attention.\nMain Results\nIt works.\nHyperparameters\nLearning rate 1e-4.\n"
            "Author Contributions\nA wrote it.\nReferences\n[1] Policy gradient methods.\n")
    paper = ScientificSectionParser().parse(SimpleNamespace(source_path="p.pdf", metadata=None, pages=[], full_text=text))
    assert [section.title for section in paper.sections] == [
        "1 Introduction", "Main Results", "Hyperparameters", "Author Contributions", "References"]
    assert paper.sections[2].content == "Learning rate 1e-4."
