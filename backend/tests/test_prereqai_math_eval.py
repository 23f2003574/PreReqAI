"""The mathematical-subtopic rules are scored on labelled equations, the gate holds floors, a degraded rule fails it, and nothing claims human review or real-paper results."""
import json

import pytest

from backend.parsing import math_subtopics
from backend.prereqai_eval import gate, math_eval

pytestmark = pytest.mark.prereqai
FLOORS = {"precision": 0.97, "recall": 0.97, "equations": 30}


def test_the_rules_score_above_the_floors_and_the_report_is_honest_about_its_data():
    report = math_eval.evaluate()
    assert report["equations"] >= 30 and report["precision"] >= FLOORS["precision"] and report["recall"] >= FLOORS["recall"], (report["false_positives"], report["false_negatives"])
    assert report["status"] == "ai_written_unreviewed" and "NOT extracted from a real PDF" in report["provenance"] and "NOT reviewed by a human" in report["provenance"]
    assert report["real_papers"] == "not annotated" and {"Softmax and normalised exponentials", "Gradients and partial derivatives"} <= set(report["per_subtopic"])


def test_the_loosest_rules_no_longer_fire_on_prose_a_sigmoid_or_an_elementwise_max():
    names = lambda text: {t for t, _, _, _ in math_subtopics.subtopics_of(text)}
    assert names("the log of the loss is plotted in the figure") == set() and "Softmax and normalised exponentials" not in names("σ(x) = 1 / (1 + e^{-x})")
    assert "Optimisation objectives (argmin and argmax)" not in names("g ← g · min(1, c / ‖g‖)") and "Optimisation objectives (argmin and argmax)" in names("V(s) = max_a Σ P(s'|s,a)[R + γV(s')]")
    assert "Expectation of a random variable" in names("∇θ J(θ) = Eτ∼πθ [Σt ∇θ log πθ(at|st) Rt]")


def test_a_deliberately_loosened_rule_is_caught_by_the_gate(monkeypatch):
    loosened = [(topic, subject, __import__("re").compile("."), why) if topic.startswith("Logarithms") else (topic, subject, pattern, why) for topic, subject, pattern, why in math_subtopics._COMPILED]
    monkeypatch.setattr(math_subtopics, "_COMPILED", loosened)
    checks = []
    gate.math_checks(checks, FLOORS)
    assert not all(c["passed"] for c in checks) and any(c["metric"] == "precision" and not c["passed"] for c in checks)
    monkeypatch.undo()
    healthy = []
    gate.math_checks(healthy, FLOORS)
    assert all(c["passed"] for c in healthy)


def test_a_dropped_rule_is_caught_by_recall(monkeypatch):
    monkeypatch.setattr(math_subtopics, "_COMPILED", [row for row in math_subtopics._COMPILED if not row[0].startswith("Gradients")])
    checks = []
    gate.math_checks(checks, FLOORS)
    assert any(c["metric"] == "recall" and not c["passed"] for c in checks)


def test_a_file_that_is_not_the_fixture_is_refused(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"format": "other"}))
    with pytest.raises(ValueError):
        math_eval.load(path)
