"""`ask --json` returns the failure envelope on stdout (as `analyze --json` and the HTTP API do); without --json it is unchanged."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _ask(paper, question, *flags):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", paper, question, *flags],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("paper, question, flags, code, stage", [
    (SAMPLE, "   ", (), 2, "input"),                         # blank question
    ("missing.pdf", "Am I ready?", (), 1, "analysis"),        # unreadable paper
    (SAMPLE, "Why calculus?", ("--topic", "Nonsense"), 2, "input"),   # unknown topic
])
def test_json_failures_are_envelopes_on_stdout(paper, question, flags, code, stage):
    run = _ask(paper, question, "--json", *flags)
    body = json.loads(run.stdout)
    assert run.returncode == code and run.stderr == ""
    assert body["status"] == "failure" and body["stage"] == stage and body["detail"]


def test_without_json_failures_stay_readable_text_on_stderr():
    run = _ask(SAMPLE, "  ")
    assert run.returncode == 2 and run.stdout == "" and run.stderr.startswith("error: the question must not be empty")


def test_a_successful_json_answer_is_unchanged():
    body = json.loads(_ask(SAMPLE, "Am I ready?", "--json").stdout)
    assert body["status"] == "success" and body["responses"]
