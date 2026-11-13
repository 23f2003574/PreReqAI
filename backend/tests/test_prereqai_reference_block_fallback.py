"""A bibliography without a recognised heading is still recognised from its structure, and left out of concept and prerequisite counts."""
from types import SimpleNamespace

import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector, subject_mentions
from backend.parsing import ParagraphSegmenter, ScientificSectionParser
from backend.parsing.scientific_section_parser import MIN_REFERENCES, _reference_block_start

pytestmark = pytest.mark.prereqai

BODY = "Abstract\nWe study a transformer with attention.\n\n1 Introduction\nAttention is useful.\n\n2 Method\nWe train it.\n\n"
NUMBERED = "".join(f"[{n}] Author{n} A. Graph attention networks and message passing {2015 + n}.\n" for n in range(1, 7))
DOTTED = "".join(f"{n}. Author{n} A., Policy gradient methods. Q-learning. Journal of Things, {2010 + n}.\n" for n in range(1, 7))
SURNAMES = ["Smith", "Jones", "Brown", "Taylor", "Wilson", "Davies", "Evans"]
AUTHOR_YEAR = "".join(f"{SURNAMES[n]}, J. B. ({2000 + n}). Denoising diffusion probabilistic models and score matching. Proc. of Things.\n" for n in range(1, 7))


def parse(text):
    document = SimpleNamespace(source_path="p.pdf", metadata=None, pages=[], full_text=text)
    return ScientificSectionParser().parse(document)


def concepts(text):
    paper = ParagraphSegmenter().segment(parse(text))
    return [c.name for c in RuleBasedConceptDetector().detect(paper).concepts]


@pytest.mark.parametrize("bibliography", [NUMBERED, DOTTED, AUTHOR_YEAR])
def test_an_unlabelled_bibliography_becomes_a_references_section_and_adds_no_concepts(bibliography):
    paper = parse(BODY + bibliography)
    assert [s.title for s in paper.sections][-1] == "References" and paper.sections[-1].content.count("\n") >= MIN_REFERENCES - 1
    assert "Method" in [s.title.split(" ")[-1] for s in paper.sections] and "We train it." in paper.sections[-2].content
    assert sorted(concepts(BODY + bibliography)) == ["Attention", "Transformer"]  # no graph, RL or diffusion concepts from cited titles


def test_an_unrecognised_heading_before_the_entries_is_still_found():
    text = BODY + "Cited Literature\n" + NUMBERED
    paper = parse(text)
    assert paper.sections[-1].title == "References" and "Cited Literature" in paper.sections[-2].content
    assert sorted(concepts(text)) == ["Attention", "Transformer"]


def test_a_heading_split_across_pages_is_still_found():
    text = BODY + "Ref-\n" + "erences\n" + NUMBERED.replace("\n[4]", "\n\n[4]")  # hyphenated heading and a page break inside the list
    assert parse(text).sections[-1].title == "References"
    assert sorted(concepts(text)) == ["Attention", "Transformer"]


def test_prerequisite_mentions_leave_out_the_unlabelled_bibliography():
    cited = "".join(f"[{n}] Author{n} A. Calculus made easy and linear algebra done right {2000 + n}.\n" for n in range(1, 7))
    paper = ParagraphSegmenter().segment(parse(BODY + "Calculus is used once.\n\n" + cited))
    found = subject_mentions(paper)
    assert found["Calculus"] == 1 and found["Linear Algebra"] == 0


def test_a_recognised_references_heading_is_unchanged_and_not_duplicated():
    paper = parse(BODY + "References\n" + NUMBERED)
    assert [s.title for s in paper.sections].count("References") == 1
    assert sorted(concepts(BODY + "References\n" + NUMBERED)) == ["Attention", "Transformer"]


def test_an_appendix_after_the_bibliography_is_kept():
    paper = parse(BODY + NUMBERED + "\nAppendix A\nProof of the claim with a softmax over the scores.\n")
    titles = [s.title for s in paper.sections]
    assert "References" in titles and titles[-1] == "Appendix A" and "Proof of the claim" in paper.sections[-1].content


def test_body_paragraphs_that_cite_are_retained():
    body = ("Abstract\nWe study a transformer.\n\n1 Introduction\nPrior work [1] used attention, as did Vaswani et al. (2017) and [2, 3] in 2019.\n"
            "Smith, J. (2020) argued the same. See [4] and [5] (2018).\n[6] shows that attention helps in 2021.\n")
    paper = parse(body)
    assert [s.title for s in paper.sections] == ["Abstract", "1 Introduction"] and sorted(concepts(body)) == ["Attention", "Transformer"]


def test_fewer_than_the_minimum_number_of_entries_is_not_a_bibliography():
    few = "".join(f"[{n}] Author{n} A. Graph attention networks {2015 + n}.\n" for n in range(1, MIN_REFERENCES))
    assert _reference_block_start("Text.\n" + few) is None


def test_entries_without_years_or_followed_by_running_text_are_not_taken():
    no_year = "".join(f"[{n}] Author{n} A. Graph attention networks.\n" for n in range(1, 8))
    assert _reference_block_start(no_year) is None
    assert _reference_block_start(NUMBERED + "x" * 600 + "\n") is None  # an over-long trailing "entry" is text
    start = _reference_block_start("Intro.\n" + NUMBERED)
    assert start == len("Intro.\n")


def test_a_numbered_list_of_headings_with_years_is_not_a_bibliography():
    headings = "\n".join(f"{n}. Results of the {2000 + n} study" for n in range(1, 4)) + "\n"
    assert _reference_block_start("Text.\n" + headings) is None
