import pytest

from backend.ingestion.arxiv_resolver import ArxivResolver


@pytest.fixture(autouse=True)
def _no_real_backoff_sleep(monkeypatch):
    """The arXiv download retries transient errors after 1s and 3s; tests that simulate a failing download
    must not wait that out for real (the retry logic itself is tested in test_prereqai_arxiv_recovery.py)."""
    monkeypatch.setattr(ArxivResolver, "RETRY_DELAYS", (0, 0))
