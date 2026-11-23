"""The command line shows the mastery estimate, its range, the refresh state and the last evidence; older profiles without those fields still print."""
import json
from datetime import timedelta

import pytest

from backend import learner_profile, spaced_review
from backend.cli import main as cli_main

pytestmark = pytest.mark.prereqai


def entry(concept, days_ago, **extra):
    seen = spaced_review.stamp(spaced_review.now() - timedelta(days=days_ago))
    return {"concept": concept, "attempts": 2, "knew": 2, "missed": 0, "streak": 2, "last_outcome": "knew", "first_seen": "2026-10-01T00:00:00Z", "last_seen": seen, "interval_hours": 72.0,
            "due": seen, "graded_attempts": 2, "graded_correct": 2, "graded_streak": 2, **extra}


def test_the_cli_prints_estimate_range_refresh_reason_and_last_evidence(tmp_path, capsys):
    path = tmp_path / "me.json"
    quiz = {"Calculus:1": entry("Calculus", 1), "Calculus:2": entry("Calculus", 1), "Probability:1": entry("Probability", 40), "Probability:2": entry("Probability", 40)}
    learner_profile.save(path, [], [], quiz)
    assert cli_main(["prerequisites", "profile", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Calculus: mastered" in out and "estimated mastery 0." in out and "range 0." in out and "not a calibrated probability" in out and "last graded answer 1 day(s) ago" in out
    assert "Probability: needs refresh" in out and "why: it was" in out and "40 days ago" in out and "answer a few questions again" in out


def test_a_profile_from_before_the_estimate_prints_only_counts(tmp_path, capsys):
    path = tmp_path / "old.json"
    quiz = {"Softmax:1": {k: v for k, v in entry("Softmax", 5).items() if not k.startswith("graded")}}
    learner_profile.save(path, [], [], quiz)
    assert cli_main(["prerequisites", "profile", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Softmax:" in out and "1 question(s)" in out and "estimated mastery" not in out and "why:" not in out


def test_describe_mastery_tolerates_missing_fields():
    line = learner_profile.describe_mastery({"concept": "X", "status": "progressing", "knew": 0, "missed": 1, "questions": 1})
    assert line == "X: progressing (0 knew, 1 missed over 1 question(s))"
