"""The file size limit also applies to a paper that is downloaded (arXiv/DOI), not only to a local path."""
import shutil
from pathlib import Path

import pytest

from backend.platform import AnalysisLimits, platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai

SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"


@pytest.fixture
def cached_arxiv_paper(tmp_path, monkeypatch):
    """A paper already in the arXiv cache, so no network is used."""
    (tmp_path / "arxiv").mkdir()
    shutil.copy(SAMPLE, tmp_path / "arxiv" / "1706.03762.pdf")
    monkeypatch.setenv("PREREQAI_CACHE_DIR", str(tmp_path))


def test_a_downloaded_paper_over_the_size_limit_ends_as_limit_exceeded_without_a_session(cached_arxiv_paper):
    before = len(session_manager.sessions)
    size = SAMPLE.stat().st_size

    outcome = platform.analyze("arXiv:1706.03762", limits=AnalysisLimits(max_file_bytes=size - 1), diagnostics=True)

    assert outcome["status"] == "limit_exceeded" and outcome["stage"] == "analysis"
    assert outcome["detail"] == f"The paper is larger than the limit of {size - 1} bytes."
    assert len(session_manager.sessions) == before


def test_a_downloaded_paper_within_the_limit_is_analysed(cached_arxiv_paper):
    outcome = platform.analyze("arXiv:1706.03762", limits=AnalysisLimits(max_file_bytes=SAMPLE.stat().st_size))

    assert outcome["status"] == "success"
