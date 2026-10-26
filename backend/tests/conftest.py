from pathlib import Path

import pytest

from backend.ingestion.arxiv_resolver import ArxivResolver


@pytest.fixture(autouse=True)
def _no_real_backoff_sleep(monkeypatch):
    """The arXiv download retries transient errors after 1s and 3s; tests that simulate a failing download
    must not wait that out for real (the retry logic itself is tested in test_prereqai_arxiv_recovery.py)."""
    monkeypatch.setattr(ArxivResolver, "RETRY_DELAYS", (0, 0))


@pytest.fixture(autouse=True)
def _run_from_the_repository_root(monkeypatch):
    """Tests name the bundled examples by repository-relative paths ("examples/prerequisites/sample-paper.pdf"), as the README
    does; pytest started from another directory (an IDE, CI with a different working-directory) must not break them."""
    monkeypatch.chdir(Path(__file__).resolve().parents[2])


PREREQAI_TEST_FILES = ("test_prerequisite_endpoint.py",)


def pytest_collection_modifyitems(items):
    """`pytest -m prereqai` runs the PreReqAI product tests (the release checks) without the large unrelated suites."""
    for item in items:
        name = item.path.name
        if name.startswith("test_prereqai_") or name in PREREQAI_TEST_FILES:
            item.add_marker(pytest.mark.prereqai)
