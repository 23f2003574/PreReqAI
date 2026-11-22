"""Extraction confidence reaches the results built on it: flagged prerequisites and steps, a guard on automatic adaptation, a monotone level on controlled degradations."""
from types import SimpleNamespace

import pytest

from backend import adaptive_plan, extraction_confidence as ec
from backend.prereqai_eval import confidence_eval

pytestmark = pytest.mark.prereqai
WORDS = ("the model learns attention weights over the input tokens and the training objective uses a probability distribution over the vocabulary " * 12).strip()


def paper(pages=8, sections=6, paragraphs=10, text=WORDS):
    ns = SimpleNamespace
    return ns(pages=[ns(page_number=n, text=text, ocr=False, ocr_error="", ocr_stopped=False, ocr_quality=None) for n in range(1, pages + 1)],
              sections=[ns(title=f"{n} Section {n}") for n in range(1, sections + 1)], references=[ns(raw_text="Smith. A paper. 2020.", reference_number=1)], citations=[ns(reference_number=1)],
              paragraphs=[ns(content=text) for _ in range(paragraphs)], concepts=[ns(name="Attention")])


def report_for(p):
    base = {"prerequisites": [{"concept": "Probability", "evidence": [{"sentence": "s"}]}, {"concept": "Calculus", "evidence": []}], "learning_plan": [{"concept": "Probability", "estimated_hours": 4}, {"concept": "Calculus", "estimated_hours": 5}],
            "math_plan": [{"concept": "Math: Integration", "estimated_hours": 1.0}], "extraction_confidence": ec.assess(p)}
    return ec.propagate(base)


def test_a_clean_extraction_flags_nothing_and_adds_only_the_effects_summary():
    r = report_for(paper())
    assert r["confidence_effects"]["level"] == "high" and r["confidence_effects"]["guard_adaptation"] is False
    assert all(p["confidence_flag"] is None for p in r["prerequisites"]) and all(s["confidence_flag"] is None for s in r["learning_plan"] + r["math_plan"])


def test_an_unreadable_text_layer_flags_every_derived_result_and_names_the_stage():
    r = report_for(paper(text=""))
    assert r["confidence_effects"]["guard_adaptation"] is True
    for item in [*r["prerequisites"], *r["learning_plan"], *r["math_plan"]]:
        assert item["confidence_flag"]["level"] == "low" and item["confidence_flag"]["stage"] == "the PDF's text layer"


def test_weak_structure_flags_evidence_only_and_does_not_guard_adaptation():
    r = report_for(paper(sections=0))
    assert r["confidence_effects"]["level"] == "low" and r["confidence_effects"]["guard_adaptation"] is False
    flags = {p["concept"]: p["confidence_flag"] for p in r["prerequisites"]}
    assert flags["Probability"]["stage"] == "section heading detection" and flags["Calculus"] is None


def test_a_report_saved_before_confidence_existed_is_unchanged():
    assert ec.propagate({"prerequisites": []}) == {"prerequisites": []}


def graded(concept):
    return [{"question_id": f"{concept}:{1 + n % 2}", "concept": concept, "outcome": "knew", "graded": True, "correct": True, "confidence": "medium"} for n in range(4)]


def test_adaptation_waits_for_the_learner_when_the_text_is_unreliable():
    r = report_for(paper(text=""))
    r["missing_prerequisites"], r["study_progress"] = [{"concept": "Probability", "importance": "essential"}], []
    assert adaptive_plan.guarded(r) is True and adaptive_plan.adapted_report(r, graded("Probability")) is r
    assert adaptive_plan.propose(r, graded("Probability"))["guarded"] is True
    r["adaptation_confirmed"] = True
    assert adaptive_plan.guarded(r) is False and adaptive_plan.adapted_report(r, graded("Probability")) is not r


def test_the_level_never_improves_as_each_kind_of_damage_grows():
    for dimension in confidence_eval.DIMENSIONS:
        rows = confidence_eval.ladder(paper(paragraphs=10), dimension)
        assert confidence_eval.monotone(rows), (dimension, rows)
        assert rows[0]["level"] == "high" and rows[-1]["level"] != "high" and [r["damage"] for r in rows] == sorted(r["damage"] for r in rows), (dimension, rows)


def test_text_that_is_mostly_noise_is_a_poor_ocr_signal_not_just_a_warning():
    rows = confidence_eval.ladder(paper(), "ocr_noise")
    assert rows[-1]["level"] == "low" and rows[-1]["damage"] > 0.6 and rows[1]["level"] == "high"


def test_the_confirm_endpoint_and_the_page_are_wired():
    from pathlib import Path

    routes = (Path(__file__).resolve().parents[1] / "api" / "session_routes.py").read_text(encoding="utf-8")
    page = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    assert "/adaptive-plan/confirm" in routes and "confidence_flag" in page and "guard_adaptation" in page
