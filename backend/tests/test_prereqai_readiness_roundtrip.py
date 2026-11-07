"""Study progress changes keep every progress-dependent part of the report consistent, reversibly and across a reload."""
import json

import pymupdf as fitz

from backend.platform import platform
from backend.session import session_manager

PROGRESS_KEYS = ("study_progress", "readiness", "study_actions", "prerequisite_tree", "study_time")


def _analyze(tmp_path):
    document = fitz.open()
    document.new_page().insert_textbox(fitz.Rect(72, 72, 540, 760), "Abstract\nWe train a policy gradient agent over a Markov decision process with a transformer.\n")
    path = tmp_path / "p.pdf"
    document.save(path)
    outcome = platform.analyze(str(path))
    return outcome["session_id"], json.loads(json.dumps(outcome["report"]))


def _reload(sid):
    session_manager.sessions.clear()
    return session_manager.get(sid).report


def test_marking_then_unmarking_restores_the_whole_report_after_a_reload(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    sid, original = _analyze(tmp_path)
    first = original["learning_plan"][0]

    platform.mark_concept_studied(sid, first["concept"])
    marked = _reload(sid)
    assert marked["readiness"]["completed_concepts"] == 1
    assert marked["study_time"]["remaining_hours"] == original["study_time"]["total_hours"] - first["estimated_hours"]
    assert first["concept"] not in [a["title"].removeprefix("Study ") for a in marked["study_actions"]]
    assert {k for k in original if marked[k] != original[k]} <= set(PROGRESS_KEYS)  # nothing else follows progress

    platform.unmark_concept_studied(sid, first["concept"])
    assert _reload(sid) == original


def test_studying_every_concept_makes_the_paper_ready_with_no_hours_left(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    sid, original = _analyze(tmp_path)
    for step in original["learning_plan"]:
        platform.mark_concept_studied(sid, step["concept"])
    report = _reload(sid)
    assert report["readiness"]["ready_to_read"] and report["readiness"]["progress_percent"] == 100
    assert report["study_time"]["remaining_hours"] == 0 and report["study_actions"] == []
