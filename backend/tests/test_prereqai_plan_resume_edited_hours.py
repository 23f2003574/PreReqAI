"""A ticked step keeps its progress on --resume even when its hours note was edited or removed by hand."""
import pytest

from backend.study_plan_markdown import studied_from_plan

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("line", [
    "- [x] 1. Calculus (~10h)",
    "- [x] 1. Calculus (~10 h)",
    "- [x] 1. Calculus (about 10h)",
    "- [x] 1. Calculus (10 hours) - [MIT](https://ocw.mit.edu/)",
    "- [x] 1. Calculus - [MIT](https://ocw.mit.edu/)",
    "- [X] 1. Calculus",
    "  * [x] 1. Calculus   ",
])
def test_ticked_steps_are_read_whatever_follows_the_name(line):
    assert studied_from_plan(line + "\n") == ["Calculus"]


@pytest.mark.parametrize("line", ["- [ ] 1. Calculus (~10h)", "- [x] Calculus (~10h)", "  - Why: - [x] 1. Calculus"])
def test_unticked_or_non_step_lines_are_not_studied(line):
    assert studied_from_plan(line + "\n") == []


def test_the_name_stops_at_the_note_not_at_the_end_of_the_line():
    assert studied_from_plan("- [x] 2. Linear Algebra (~12h) - [MIT 18.06](https://x.org/)\n") == ["Linear Algebra"]
