"""On a paper where no known concept was found, study/time/readiness questions say so instead of "You are ready (100%)" or a
placeholder; a normal paper's answers are unchanged."""
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _ask(paper, question):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", str(paper), question],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


@pytest.fixture(scope="module")
def bees(tmp_path_factory):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Study of Bees\n\nAbstract\nBees are insects that make honey.\n", fontsize=11)
    path = tmp_path_factory.mktemp("bees") / "bees.pdf"
    path.write_bytes(document.tobytes())
    return path


@pytest.mark.parametrize("question", ["Am I ready?", "What should I study first?", "How long will it take?"])
def test_a_paper_without_detected_concepts_gets_an_honest_answer(bees, question):
    answer = _ask(bees, question)
    assert answer.startswith("No concepts this release knows were detected") and "You are ready" not in answer


def test_a_normal_paper_is_unchanged():
    assert _ask(SAMPLE, "Am I ready?").startswith("You are not ready to read the paper yet.")
    assert _ask(SAMPLE, "What should I study first?").startswith("Study these in order")
    assert _ask(SAMPLE, "How long will it take?").startswith("Plan about 55 hours")
