from backend.pipeline import (
    ResearchPaperPipeline,
)


def test_pipeline_initializes():

    pipeline = ResearchPaperPipeline()

    assert pipeline is not None
