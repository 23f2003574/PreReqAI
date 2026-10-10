from backend.pipeline import (
    InteractiveLearningPipeline,
)


def test_pipeline_exists():

    pipeline = (
        InteractiveLearningPipeline()
    )

    assert pipeline is not None
