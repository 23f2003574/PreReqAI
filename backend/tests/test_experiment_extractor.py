from backend.parsing import ExperimentExtractor

from backend.models import (
    Paper,
    PaperSection,
)


def test_experiment_extractor_matches_experiment_sections():

    extractor = ExperimentExtractor()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        sections=[
            PaperSection(
                title="Introduction",
                content="This paper studies...",
            ),
            PaperSection(
                title="Results",
                content="We evaluate on WMT 2014...",
            ),
        ],
    )

    result = extractor.extract(paper)

    assert len(result.experiments) == 1
    assert result.experiments[0].title == "Results"
    assert (
        result.experiments[0].description
        == "We evaluate on WMT 2014..."
    )


def test_experiment_extractor_returns_empty_when_no_match():

    extractor = ExperimentExtractor()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        sections=[
            PaperSection(
                title="Introduction",
                content="This paper studies...",
            ),
        ],
    )

    result = extractor.extract(paper)

    assert result.experiments == []
