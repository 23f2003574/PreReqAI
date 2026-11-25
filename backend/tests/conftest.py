import os
from pathlib import Path

import pytest

from backend.ingestion.arxiv_resolver import ArxivResolver

os.environ["PREREQAI_ALLOW_TESTSERVER"] = "1"  # the test client's Host is "testserver", accepted only when this is set (see backend/security.py)


@pytest.fixture(autouse=True)
def _no_real_backoff_sleep(monkeypatch):
    """The arXiv download retries transient errors after 1s and 3s; tests that simulate a failing download
    must not wait that out for real (the retry logic itself is tested in test_prereqai_arxiv_recovery.py)."""
    monkeypatch.setattr(ArxivResolver, "RETRY_DELAYS", (0, 0))


@pytest.fixture(autouse=True)
def _parse_in_process_by_default(monkeypatch):
    """Most tests patch pipeline stages or OCR in this process, which a worker process cannot see; the worker path is tested by test_prereqai_isolated_parse.py, which removes this."""
    monkeypatch.setenv("PREREQAI_PARSE_INPROCESS", "1")


@pytest.fixture(autouse=True)
def _own_analysis_slots(monkeypatch, tmp_path_factory):
    """The analysis slots are shared by every process on the computer (backend/analysis_slots.py); parallel test workers must not take each other's slots."""
    monkeypatch.setenv("PREREQAI_SLOTS_DIR", str(tmp_path_factory.mktemp("slots")))


@pytest.fixture(autouse=True)
def _empty_analysis_cache(monkeypatch):
    """The analysis cache is a process-wide singleton: an earlier test's analysis of the bundled paper must not stand in for the pipeline run a
    later test (stage cancellation, time limits, patched stages) is about. The cache's own tests fill it on purpose."""
    from backend.analysis_cache import analysis_cache

    monkeypatch.delenv("PREREQAI_ANALYSIS_CACHE_DIR", raising=False)
    analysis_cache.clear()


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
