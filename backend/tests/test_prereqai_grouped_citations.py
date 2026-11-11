import pytest

from backend.models import Paper, Paragraph
from backend.parsing import CitationExtractor


def _numbers(text):
    paper = Paper(source_path="p.pdf", metadata=None, paragraphs=[Paragraph(paragraph_id=1, section_title="Introduction", content=text)])
    return [(c.citation_id, c.reference_number) for c in CitationExtractor().extract(paper).citations]


@pytest.mark.parametrize("text, expected", [
    ("Prior work [13].", [13]),
    ("Prior work [1, 2].", [1, 2]),
    ("Prior work [1,2,3].", [1, 2, 3]),
    ("Prior work [1-3].", [1, 2, 3]),
    ("Prior work [1–3].", [1, 2, 3]),
    ("Prior work [1, 3-5].", [1, 3, 4, 5]),
    ("Prior work [7] and [2, 4].", [7, 2, 4]),
    ("Prior work [3-3].", [3]),
])
def test_single_grouped_and_range_citations_expand_in_order(text, expected):
    found = _numbers(text)
    assert [number for _, number in found] == expected
    assert [cid for cid, _ in found] == list(range(1, len(expected) + 1))


@pytest.mark.parametrize("text", ["Prior work [5-3].", "Prior work [1-9999].", "Prior work [1,, 2].", "Prior work [a-b].", "Prior work [1-].", "Prior work []."])
def test_malformed_or_reversed_ranges_yield_no_citation(text):
    assert _numbers(text) == []


def test_reversed_range_in_a_list_keeps_the_valid_parts():
    assert [n for _, n in _numbers("See [1, 5-3, 7].")] == [1, 7]
