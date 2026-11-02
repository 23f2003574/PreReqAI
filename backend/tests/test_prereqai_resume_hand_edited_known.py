"""A hand-edited "Already known" line (comma separated, as with --known; any letter case) is honoured on --resume."""
import pytest

from backend.study_plan_markdown import known_from_plan

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("line", [
    "Already known: Linear Algebra; Calculus",       # as written by plan_markdown
    "Already known: Linear Algebra, Calculus",      # hand-edited with commas
    "already known: Linear Algebra,Calculus",       # lower case, no space
    "Already known:   Linear Algebra ; Calculus ,",  # stray spacing and a trailing separator
])
def test_known_names_are_split_however_they_are_separated(line):
    assert known_from_plan(f"# Study plan: X\n\n{line}\n\n- [ ] 1. Probability (~10h)\n") == ["Linear Algebra", "Calculus"]


def test_plan_without_a_known_line_records_nothing():
    assert known_from_plan("# Study plan: X\n\n- [ ] 1. Probability (~10h)\nWe already know it.\n") == []
