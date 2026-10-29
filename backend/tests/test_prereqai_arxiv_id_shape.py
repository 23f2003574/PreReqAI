"""Only a well-formed arXiv identifier (YYMM.NNNN or YYMM.NNNNN, or an old-style one) is accepted, so a typo is rejected
before any download is attempted."""
import pytest

from backend.ingestion.research_source_detector import ResearchSourceDetector

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("source, identifier", [
    ("arXiv:1706.03762", "1706.03762"),
    ("arXiv:0704.0001", "0704.0001"),
    ("https://arxiv.org/abs/1706.03762v5", "1706.03762v5"),
    ("arXiv:hep-th/9901001", "hep-th/9901001"),
])
def test_well_formed_identifiers_are_accepted(source, identifier):
    detected = ResearchSourceDetector().detect(source)
    assert (detected.source_type, detected.identifier) == ("arxiv", identifier)


@pytest.mark.parametrize("source", [
    "arXiv:1.1",
    "arXiv:1706.037",
    "arXiv:1706.0376200",
    "arXiv:17.03762",
    "https://arxiv.org/abs/170.03762",
])
def test_malformed_identifiers_are_rejected_before_any_download(source):
    with pytest.raises(ValueError, match="Unsupported research source"):
        ResearchSourceDetector().detect(source)
