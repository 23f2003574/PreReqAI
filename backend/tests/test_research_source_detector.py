from backend.ingestion import (
    ResearchSourceDetector,
)


def test_detects_pdf():

    detector = ResearchSourceDetector()

    source = detector.detect(
        "papers/attention.pdf"
    )

    assert source.source_type == "pdf"


def test_detects_arxiv():

    detector = ResearchSourceDetector()

    source = detector.detect(
        "https://arxiv.org/abs/1706.03762"
    )

    assert source.source_type == "arxiv"


def test_detects_doi():

    detector = ResearchSourceDetector()

    source = detector.detect(
        "https://doi.org/10.1038/s41586-020-2649-2"
    )

    assert source.source_type == "doi"
