"""A saved plan re-saved by an editor that adds a UTF-8 BOM (Windows Notepad) is still a study plan: resume and --plan-file accept it."""
from pathlib import Path

from starlette.testclient import TestClient

from backend.cli_prerequisites import _apply_resume, _plan_file_problem
from backend.main import app

PLAN = "# Study plan: X\n\n1 of 1 studied, about 0h left.\n\n- [x] 1. Probability (~10h)\n"


def _bom_plan(tmp_path):
    path = tmp_path / "plan.md"
    path.write_bytes(b"\xef\xbb\xbf" + PLAN.encode())
    return path


def test_cli_resume_reads_a_plan_with_a_bom(tmp_path):
    args = type("Args", (), {"resume": str(_bom_plan(tmp_path)), "studied": [], "known": []})()
    assert _apply_resume(args) is True
    assert args.studied == ["Probability"]


def test_plan_file_overwrites_a_bom_plan_but_not_other_files(tmp_path):
    assert _plan_file_problem(_bom_plan(tmp_path)) is None
    other = tmp_path / "notes.md"
    other.write_bytes(b"\xef\xbb\xbfmy notes, not a plan")
    assert "not a saved study plan" in _plan_file_problem(other)


def test_http_resume_reads_a_plan_with_a_bom(tmp_path):
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        response = client.post("/api/prerequisites/analyze", files={
            "paper": ("p.pdf", handle, "application/pdf"), "resume": ("plan.md", Path(_bom_plan(tmp_path)).read_bytes(), "text/markdown")})
    assert response.status_code == 200
    progress = {i["concept"]: i["completed"] for i in client.get(f"/api/session/{response.json()['session_id']}").json()["study_progress"]}
    assert progress["Probability"] is True


def test_is_saved_plan_is_the_single_check_for_every_resume_surface():
    from backend.study_plan_markdown import is_saved_plan

    assert is_saved_plan(PLAN) and is_saved_plan("﻿" + PLAN) and is_saved_plan("\n\r\n  " + PLAN)
    assert not is_saved_plan("") and not is_saved_plan("# Notes\n" + PLAN) and not is_saved_plan("Study plan: X")
