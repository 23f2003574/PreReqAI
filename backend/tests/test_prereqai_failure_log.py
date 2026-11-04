"""A failed analysis leaves one server-side log line naming the status, stage, failing pipeline stage, error type and elapsed
time -- and nothing that echoes the paper, the error message, the file path or the learner's input."""
import logging

import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.pipeline import research_paper_pipeline as pipeline

pytestmark = pytest.mark.prereqai

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _upload(client, data=None):
    with open(SAMPLE, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data or {})


def test_a_stage_failure_is_logged_with_its_stage_and_error_type_but_not_its_message(monkeypatch, caplog):
    def boom(self, *args, **kwargs):
        raise KeyError("secret-token-from-the-paper")

    monkeypatch.setattr(pipeline.RuleBasedConceptDetector, "detect", boom)

    with caplog.at_level(logging.INFO, logger="prereqai.analysis"):
        response = _upload(TestClient(app), {"known": "Calculus"})

    assert response.status_code == 400
    records = [r for r in caplog.records if r.name == "prereqai.analysis"]
    assert len(records) == 1
    line = records[0].getMessage()
    assert records[0].levelno == logging.WARNING
    assert "analysis failure: stage=analysis failed_stage=concept_detector error=KeyError elapsed=" in line
    assert line.endswith("s")
    for private in ("secret-token-from-the-paper", "Calculus", "sample-paper", "/tmp"):
        assert private not in line


def test_a_successful_analysis_logs_nothing(caplog):
    with caplog.at_level(logging.INFO, logger="prereqai.analysis"):
        assert _upload(TestClient(app)).status_code == 200

    assert [r for r in caplog.records if r.name == "prereqai.analysis"] == []
