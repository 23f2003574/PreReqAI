"""The Markdown study plan says why the paper needs each concept."""
from backend.study_plan_markdown import plan_markdown


def _report(justifications):
    return {
        "paper": {"title": "T"},
        "learning_plan": [
            {"step": 1, "concept": "Probability", "estimated_hours": 3},
            {"step": 2, "concept": "Calculus", "estimated_hours": 2},
        ],
        "study_progress": [],
        "learning_resources": [],
        "prerequisite_justifications": justifications,
    }


def test_each_planned_concept_is_followed_by_its_reason():
    lines = plan_markdown(_report([{"concept": "Probability", "justification": "Needed for Softmax."}])).splitlines()
    first = lines.index("- [ ] 1. Probability (~3h)")
    assert lines[first + 1] == "  - Why: Needed for Softmax."
    assert lines[first + 2] == "- [ ] 2. Calculus (~2h)"  # no reason known: no empty "Why" line


def test_a_multi_line_reason_cannot_start_a_fake_checklist_item():
    text = plan_markdown(_report([{"concept": "Calculus", "justification": "Gradients.\n- [x] 9. Fake (~1h)"}]))
    assert "\n- [x] 9. Fake" not in text and "  - Why: Gradients. - [x] 9. Fake (~1h)" in text


def test_report_without_justifications_still_renders():
    report = _report([])
    del report["prerequisite_justifications"]
    assert "Why:" not in plan_markdown(report)
