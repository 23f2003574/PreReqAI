"""Profile-aware study planning: a saved profile shapes the plan, the workload and the explanations, and nothing changes without one."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import cli, learner_profile as lp
from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


def _cli(capsys, *args):
    assert cli.main(["prerequisites", "analyze", SAMPLE, "--json", *args]) == 0
    return json.loads(capsys.readouterr().out)


def _post(**data):
    with open(SAMPLE, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data).json()


@pytest.fixture(autouse=True)
def _clean():
    session_manager.sessions.clear()
    yield
    session_manager.sessions.clear()


def test_two_learners_with_different_knowledge_get_different_plans(tmp_path, monkeypatch):
    monkeypatch.setenv(lp.PROFILE_DIR_ENV, str(tmp_path))
    lp.save(tmp_path / "ada.json", ["Linear Algebra", "Probability", "Calculus"], [])
    ada, newcomer = _post(profile="ada")["report"]["personalised_plan"], _post(profile="newcomer")["report"]["personalised_plan"]
    left = lambda plan: [o["concept"] for o in plan["outstanding"]]
    assert "Linear Algebra" not in left(ada) and "Linear Algebra" in left(newcomer) and len(left(ada)) < len(left(newcomer))
    assert {c["concept"] for c in ada["covered"]} == {"Linear Algebra", "Probability", "Calculus"} and newcomer["covered"] == []
    assert all(c["from"] == "your learner profile" for c in ada["covered"])
    assert ada["workload"]["remaining_hours"] < newcomer["workload"]["remaining_hours"]
    assert newcomer["workload"]["known_hours"] == 0 and ada["workload"]["known_hours"] > 0


def test_a_saved_profile_shapes_the_next_analysis_and_remaining_work_reflects_it(tmp_path, capsys):
    path = str(tmp_path / "me.json")
    first = _cli(capsys, "--profile", path, "--known", "Linear Algebra", "--studied", "Probability")
    second = _cli(capsys, "--profile", path)  # nothing entered this time
    plan = second["report"]["personalised_plan"]
    assert {c["concept"]: c["status"] for c in plan["covered"]} == {"Linear Algebra": "known", "Probability": "studied"}
    assert not {"Linear Algebra", "Probability"} & set(plan["path"])  # covered subjects are not on the path
    outstanding = {o["concept"]: o for o in plan["outstanding"]}
    assert second["report"]["study_time"]["remaining_hours"] == sum(o["estimated_hours"] for o in outstanding.values())
    assert plan["workload"]["remaining_hours"] == second["report"]["study_time"]["remaining_hours"]  # the one scheduler's own figure
    assert first["report"]["personalised_plan"]["workload"]["remaining_hours"] == plan["workload"]["remaining_hours"]


def test_outstanding_work_is_prioritised_and_explained_from_the_paper(tmp_path, capsys):
    plan = _cli(capsys, "--profile", str(tmp_path / "p.json"))["report"]["personalised_plan"]
    assert [o["priority"] for o in plan["outstanding"]] == list(range(1, len(plan["outstanding"]) + 1))
    rank = {"essential": 0, "supporting": 1}
    keys = [(rank[o["importance"]], {"strong": 0, "moderate": 1, "weak": 2}[o["evidence_strength"]]) for o in plan["outstanding"]]
    assert keys == sorted(keys)  # essential and well-supported first
    top = plan["outstanding"][0]
    assert top["why"].startswith("Required to understand") and "Evidence in the paper:" in top["why"] and top["needed_by"]


def test_shared_prerequisites_are_planned_and_scheduled_once(tmp_path, capsys):
    report = _cli(capsys, "--profile", str(tmp_path / "p.json"))["report"]
    plan = report["personalised_plan"]
    names = [o["concept"] for o in plan["outstanding"]]
    assert len(names) == len(set(names)) and len(plan["path"]) == len(set(plan["path"]))
    scheduled = [item["concept"] for day in report["study_time"]["schedule"] for item in day["items"]]
    assert sorted(set(scheduled)) == sorted(names)
    for outstanding in plan["outstanding"]:  # a long step may span several days, but its hours are scheduled exactly once
        spent = sum(item["hours"] for day in report["study_time"]["schedule"] for item in day["items"] if item["concept"] == outstanding["concept"])
        assert abs(spent - outstanding["estimated_hours"]) < 0.01, outstanding["concept"]
    shared = max(plan["outstanding"], key=lambda o: len(o["needed_by"]))
    assert len(shared["needed_by"]) > 1 and names.count(shared["concept"]) == 1


def test_without_a_profile_nothing_changes(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(lp.PROFILE_DIR_ENV, raising=False)
    plain = _cli(capsys, "--known", "Linear Algebra")
    assert "personalised_plan" not in plain["report"] and "profile" not in plain
    body = _post(profile="me", known="Linear Algebra")  # profiles are off on the server: the field is ignored
    assert "personalised_plan" not in body["report"]
    assert "personalised_plan" not in client.get(f"/api/session/{body['session_id']}").json()


def test_api_and_session_agree_and_progress_keeps_the_plan_current(tmp_path, monkeypatch):
    monkeypatch.setenv(lp.PROFILE_DIR_ENV, str(tmp_path))
    body = _post(profile="me", known="Linear Algebra")
    sid, plan = body["session_id"], body["report"]["personalised_plan"]
    assert client.get(f"/api/session/{sid}").json()["personalised_plan"] == plan
    step = plan["outstanding"][0]["concept"]
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": step})
    later = client.get(f"/api/session/{sid}").json()["personalised_plan"]
    assert step not in [o["concept"] for o in later["outstanding"]] and any(c["concept"] == step and c["from"] == "this analysis" for c in later["covered"])
    assert later["workload"]["remaining_hours"] < plan["workload"]["remaining_hours"] and later["sources"] == plan["sources"]


def test_a_restored_profile_and_session_do_not_lose_progress(tmp_path, monkeypatch):
    monkeypatch.setenv(lp.PROFILE_DIR_ENV, str(tmp_path / "profiles"))
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    first = _post(profile="me", known="Linear Algebra", studied="Probability")
    session_manager.sessions.clear()  # a restart: the session is read from disk, the profile from its file
    restored = client.get(f"/api/session/{first['session_id']}").json()["personalised_plan"]
    assert restored == first["report"]["personalised_plan"]
    again = _post(profile="me")["report"]["personalised_plan"]
    assert {c["concept"] for c in again["covered"]} == {"Linear Algebra", "Probability"}


def test_the_cli_and_the_web_page_show_the_same_plan(tmp_path, capsys):
    path = str(tmp_path / "me.json")
    assert cli.main(["prerequisites", "analyze", SAMPLE, "--profile", path, "--known", "Linear Algebra"]) == 0
    out = capsys.readouterr().out
    plan = _cli(capsys, "--profile", path)["report"]["personalised_plan"]
    assert f"for you (learner profile {path})" in out and "covered: Linear Algebra (known, from this analysis)" in out
    assert plan["outstanding"] and all(f"{o['priority']}. {o['concept']} (~{o['estimated_hours']}h): {o['why']}" in out for o in plan["outstanding"])
    page = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    for fragment in ('id="mine"', "function renderMine()", "report.personalised_plan", "body.personalised_plan", 'id="profile"', 'data.append("profile"'):
        assert fragment in page, fragment
    assert "innerHTML" not in page
