"""Every question the placeholder's hint advertises really is answered by the built-in tutor (the hint cannot drift)."""
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tutor.rule_based_tutor import ANSWERABLE_HINT

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = "tutoring model has not yet been configured"
EXAMPLES = {
    "What is <concept>?": "What is softmax?",
    "What should I study first?": "What should I study first?",
    "How long will it take?": "How long will it take?",
    "How difficult is it?": "How difficult is it?",
    "Am I ready?": "Am I ready?",
    "How much have I completed?": "How much have I completed?",
    "Which prerequisites does <concept> need?": "Which prerequisites does Softmax need?",
    "Which equations are in the paper?": "Which equations are in the paper?",
    "Summarize this paper": "Summarize this paper",
    "Quiz me": "Quiz me",
}


def _ask(question):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask",
                          "examples/prerequisites/sample-paper.pdf", question],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


@pytest.mark.parametrize("advertised", list(EXAMPLES))
def test_each_advertised_question_is_in_the_hint_and_is_answered(advertised):
    assert f"'{advertised}'" in ANSWERABLE_HINT
    assert PLACEHOLDER not in _ask(EXAMPLES[advertised])
