"""A failed arXiv/DOI download is reported as a download problem, not as a bad PDF upload; `ask` documents the same sources as `analyze`."""
import subprocess
import sys
from pathlib import Path

import requests

from backend.platform.prereqai_platform import _stopped_outcome

ROOT = Path(__file__).resolve().parents[2]


def test_connection_failure_hint_names_the_download():
    outcome = _stopped_outcome(requests.exceptions.ConnectionError("tunnel failed"))
    assert outcome["status"] == "failure" and "could not be downloaded" in outcome["hint"]
    assert "Upload a text-based PDF" not in outcome["hint"]


def test_other_failures_keep_their_hints():
    assert _stopped_outcome(RuntimeError("bad pdf"))["hint"] == "Upload a text-based PDF research paper."
    assert "timed out" in _stopped_outcome(requests.exceptions.Timeout("slow"))["detail"]


def test_ask_help_accepts_the_same_sources_as_analyze():
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", "--help"],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert "arXiv" in run.stdout and "DOI" in run.stdout
