"""Fixed-phrase unnumbered headings such as "Motivation" or "Case Study" start a section; sentences that merely begin with them do not."""
import pytest

from backend.parsing.scientific_section_parser import SECTION_PATTERN

pytestmark = pytest.mark.prereqai

HEADINGS = ["Motivation", "Problem Definition", "Baselines", "Contributions", "Architecture", "Model Training",
            "Case Study", "Case Studies", "Setup", "Implementation", "Error Analysis", "Task Description", "3.1 Setup"]


@pytest.mark.parametrize("line", HEADINGS)
def test_the_heading_is_recognised(line):
    assert SECTION_PATTERN.fullmatch(line)


@pytest.mark.parametrize("line", ["Setup is easy.", "The architecture uses attention", "case study of 3 models"])
def test_sentences_are_not_headings(line):
    assert not SECTION_PATTERN.fullmatch(line)
