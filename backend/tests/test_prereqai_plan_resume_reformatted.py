"""A saved plan that an editor or formatter reformatted (`*` or `+` bullets, indentation, CRLF) still restores its ticked progress."""
import pytest

from backend.study_plan_markdown import known_from_plan, studied_from_plan

pytestmark = pytest.mark.prereqai

PLAN = (
    "# Study plan: Paper\n\nAlready known: Calculus\n\n"
    "- [x] 1. Linear Algebra (~12h) - link\n"
    "- [ ] 2. Probability (~10h)\n"
    "- [X] 3. Neural Networks (~15h)\n"
)


def test_the_original_format_is_unchanged():
    assert studied_from_plan(PLAN) == ["Linear Algebra", "Neural Networks"]


def test_star_plus_and_indented_bullets_restore_the_same_progress():
    assert studied_from_plan(PLAN.replace("- [", "* [")) == ["Linear Algebra", "Neural Networks"]
    assert studied_from_plan(PLAN.replace("- [", "+ [")) == ["Linear Algebra", "Neural Networks"]
    assert studied_from_plan(PLAN.replace("- [", "  - [")) == ["Linear Algebra", "Neural Networks"]
    assert studied_from_plan(PLAN.replace("\n", "\r\n")) == ["Linear Algebra", "Neural Networks"]
    assert known_from_plan(PLAN.replace("Already", "  Already")) == ["Calculus"]


def test_unticked_and_unrelated_lines_are_not_studied():
    assert studied_from_plan("# Study plan: P\n\n* [ ] 1. Probability (~10h)\nSee [x] 2. Calculus (~1h)\n") == []
