import pytest

from backend.parsing.reference_metadata_parser import ReferenceMetadataParser


def _parse(text):
    result = ReferenceMetadataParser().parse(text)
    return result["authors"], result["title"], result["year"]


def test_initials_before_the_surname_do_not_end_the_author_list():
    assert _parse("A. Vaswani, N. Shazeer, and J. Uszkoreit. Attention is all you need. In NeurIPS, 2017.") == (
        ["A. Vaswani", "N. Shazeer", "J. Uszkoreit"], "Attention is all you need", 2017)


def test_surname_and_initials_stay_one_author():
    assert _parse("Vaswani, A., Shazeer, N. Attention is all you need. NeurIPS 2017.") == (
        ["Vaswani, A.", "Shazeer, N"], "Attention is all you need", 2017)


@pytest.mark.parametrize("text, authors", [
    ("Vaswani A, Shazeer N. Attention is all you need. NeurIPS 2017.", ["Vaswani A", "Shazeer N"]),
    ("Kipf T and Welling M. Semi-supervised classification. ICLR 2017.", ["Kipf T", "Welling M"]),
])
def test_existing_styles_are_unchanged(text, authors):
    parsed_authors, title, _ = _parse(text)
    assert parsed_authors == authors and title in ("Attention is all you need", "Semi-supervised classification")


def test_a_title_right_after_the_last_initial_still_starts_the_title():
    assert _parse("Smith, J. Deep learning for graphs. ICML 2019.")[1] == "Deep learning for graphs"
