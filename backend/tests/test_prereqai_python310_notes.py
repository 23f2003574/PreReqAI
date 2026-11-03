"""BaseException.add_note is Python 3.11+, but the project supports 3.10 (CI runs it): generation failures are annotated
through one helper that keeps the same `__notes__` list on both. CI's 3.10 job runs the real failure paths; this pins
the fallback on every interpreter."""
import pytest

from backend.api_generation.notes import add_note

pytestmark = pytest.mark.prereqai


def test_notes_are_kept_in_order_on_a_real_exception():
    error = ValueError("boom")

    add_note(error, "first")
    add_note(error, "second")

    assert error.__notes__ == ["first", "second"]


def test_an_object_without_add_note_gets_the_same_notes_list():
    class WithoutAddNote:  # what a Python 3.10 exception looks like to the helper
        pass

    legacy = WithoutAddNote()
    add_note(legacy, "one")
    add_note(legacy, "two")

    assert legacy.__notes__ == ["one", "two"]
