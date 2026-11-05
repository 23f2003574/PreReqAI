"""A stage that hands over the wrong kind of value fails at that stage, naming it, not one stage later with an obscure error."""
from pathlib import Path

import pytest

from backend.pipeline.research_paper_pipeline import ResearchPaperPipeline

pytestmark = pytest.mark.prereqai

PAPER = str(Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf")


@pytest.mark.parametrize("component, method, bad, stage, returned", [
    ("source_detector", "detect", "not-a-source", "source_detector", "str"),
    ("source_resolver", "resolve", 42, "source_resolver", "int"),
    ("ingestion", "ingest", {"pages": []}, "ingestion", "dict"),
])
def test_a_wrong_early_output_fails_at_the_stage_that_produced_it(monkeypatch, component, method, bad, stage, returned):
    pipeline = ResearchPaperPipeline()
    monkeypatch.setattr(getattr(pipeline, component), method, lambda *args: bad)
    with pytest.raises(TypeError) as caught:
        pipeline.run(PAPER)
    assert caught.value.failed_stage == stage
    assert f"stage {stage} returned {returned}" in str(caught.value)


def test_the_real_early_stages_still_pass_their_checks():
    result = ResearchPaperPipeline().run(PAPER)
    assert "ingestion" in result.timings and result.report
