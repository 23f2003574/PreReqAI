"""--max-seconds / PREREQAI_MAX_ANALYSIS_SECONDS holds while a download is being retried: a failing arXiv download does not
keep retrying (delays and repeated attempts) past the limit, and the run ends as limit_exceeded, not as a network failure."""
import time

import pytest
import requests

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.platform import AnalysisLimits, PreReqAIPlatform

pytestmark = pytest.mark.prereqai


@pytest.fixture
def failing_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "arxiv")
    monkeypatch.setattr(ArxivResolver, "RETRY_DELAYS", (0.3, 0.3, 0.3, 0.3))
    attempts = []

    def down(*args, **kwargs):
        attempts.append(time.monotonic())
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(requests, "get", down)
    return attempts


def test_a_time_limit_stops_the_download_retries_and_reports_limit_exceeded(failing_downloads):
    started = time.monotonic()
    outcome = PreReqAIPlatform().analyze("arXiv:1706.03762", limits=AnalysisLimits(max_seconds=0.2))

    assert outcome["status"] == "limit_exceeded"
    assert "time limit of 0.2 seconds" in outcome["detail"]
    assert len(failing_downloads) == 1  # the retry after the deadline was never made
    assert time.monotonic() - started < 1.0


def test_without_a_limit_the_download_is_still_retried_to_the_end(failing_downloads):
    outcome = PreReqAIPlatform().analyze("arXiv:1706.03762")

    assert outcome["status"] == "failure"
    assert len(failing_downloads) == 5
