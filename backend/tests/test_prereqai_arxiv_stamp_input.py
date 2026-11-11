import pytest

from backend.ingestion.research_source_detector import ResearchSourceDetector


@pytest.mark.parametrize("pasted, identifier", [
    ("arXiv:1706.03762 [cs.CL]", "1706.03762"),
    ("arXiv:1706.03762v5 [cs.CL] 6 Dec 2017", "1706.03762v5"),
    ("arXiv:1706.03762v5 [cs.CL] 6 December 2017", "1706.03762v5"),
    ("arxiv:cs/0112017v1 [cs.LG]", "cs/0112017v1"),
    ("arXiv:2301.00001 [stat.ML]", "2301.00001"),
    ("arXiv:1706.03762", "1706.03762"),
])
def test_the_arxiv_stamp_on_a_paper_resolves_to_its_identifier(pasted, identifier):
    source = ResearchSourceDetector().detect(pasted)
    assert (source.source_type, source.identifier) == ("arxiv", identifier)


@pytest.mark.parametrize("pasted", ["arXiv:1706.03762 [cs.CL] trailing words", "arXiv:1706.03762 [cs.CL", "1706.03762 [cs.CL]", "arXiv: [cs.CL]"])
def test_other_text_is_still_rejected(pasted):
    with pytest.raises(ValueError):
        ResearchSourceDetector().detect(pasted)
