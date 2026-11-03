"""The shared tutor keeps each request's prompt to that request's thread: concurrent sessions cannot read or
overwrite one another's prompt."""
import threading
from types import SimpleNamespace

import pytest

from backend.tutor.rule_based_tutor import RuleBasedTutor

pytestmark = pytest.mark.prereqai


class _Builder:
    def build(self, session, paper, context, question, mode):
        return f"prompt for {question}"


def test_concurrent_requests_each_see_only_their_own_prompt():
    tutor = RuleBasedTutor()
    tutor.prompt_builder = _Builder()
    both_built = threading.Barrier(2, timeout=10)
    seen = {}

    def ask(name):
        try:
            tutor.answer(None, SimpleNamespace(concepts=[]), None, f"question of {name}", "intuition")
        except Exception:  # only the stored prompt matters here, not the (stubbed paper's) answer
            pass
        both_built.wait()  # the other request has now built (and stored) its own prompt
        seen[name] = tutor.last_prompt

    threads = [threading.Thread(target=ask, args=(n,)) for n in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert seen == {"A": "prompt for question of A", "B": "prompt for question of B"}


def test_a_new_tutor_has_no_prompt_yet():
    assert RuleBasedTutor().last_prompt is None
