import pytest

from backend.study_plan_markdown import studied_from_plan

HEAD = "# Study plan: X\n\n"


@pytest.mark.parametrize("line, concept", [
    ("- [x] 1. Probability (~10h)", "Probability"),
    ("- [x] 1) Probability (~10h)", "Probability"),
    ("- [x] Probability (~10h)", "Probability"),
    ("1. [x] Probability (~10h)", "Probability"),
    ("- [x] 1. Probability \u2014 10h", "Probability"),
    ("- [X] 2.  Probability  (~10h)", "Probability"),
    ("- [x] 1. Linear Algebra (~12h) - [Course](http://x)", "Linear Algebra"),
    ("- [x] 4. Q-Learning (~8h)", "Q-Learning"),
])
def test_a_ticked_step_survives_a_hand_edit(line, concept):
    assert studied_from_plan(HEAD + line + "\n") == [concept]


@pytest.mark.parametrize("line", ["- [ ] 1. Probability (~10h)", "- [x]", "Probability is ticked", "- [x] "])
def test_unticked_or_malformed_lines_restore_nothing(line):
    assert studied_from_plan(HEAD + line + "\n") == []
