from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
client = TestClient(app)


def _session():
    with SAMPLE.open("rb") as handle:
        outcome = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    return outcome["session_id"], outcome["report"]


def test_marking_known_removes_concept_from_plan_and_persists_in_session():
    session_id, report = _session()
    plan = [item["concept"] for item in report["study_progress"]]
    url = f"/api/prerequisites/sessions/{session_id}/known"
    done = client.post(url, params={"concept": f" {plan[0].upper()} "}).json()
    assert done["status"] == "success"
    remaining = [item["concept"] for item in done["report"]["study_progress"]]
    assert plan[0] not in remaining and len(remaining) == len(plan) - 1
    stored = client.get(f"/api/session/{session_id}").json()
    assert plan[0] not in [item["concept"] for item in stored["study_progress"]]


def test_known_reports_unknown_session_and_concept():
    session_id, _ = _session()
    url = f"/api/prerequisites/sessions/{session_id}/known"
    assert client.post("/api/prerequisites/sessions/nope/known", params={"concept": "x"}).status_code == 404
    assert client.post(url, params={"concept": "Cooking"}).status_code == 422


def test_marking_known_keeps_progress_on_other_studied_concepts():
    session_id, report = _session()
    plan = [item["concept"] for item in report["study_progress"]]
    base = f"/api/prerequisites/sessions/{session_id}"
    client.post(f"{base}/studied", params={"concept": plan[0]})
    client.post(f"{base}/studied", params={"concept": plan[1]})
    done = client.post(f"{base}/known", params={"concept": plan[1]}).json()["report"]  # studied, then known: leaves the plan
    assert [(i["concept"], i["completed"]) for i in done["study_progress"]][0] == (plan[0], True)
    assert plan[1] not in [i["concept"] for i in done["study_progress"]]
    assert done["readiness"]["completed_concepts"] == 1
    assert client.get(f"/api/session/{session_id}").json()["readiness"]["completed_concepts"] == 1


def test_studied_at_analysis_and_studied_later_give_the_same_progress_sections():
    from backend.platform.prereqai_platform import PROGRESS_REPORT_KEYS
    with SAMPLE.open("rb") as handle:
        upfront = client.post("/api/prerequisites/analyze", data={"studied": ["Probability"]},
                              files={"paper": ("p.pdf", handle, "application/pdf")}).json()["report"]
    session_id, _ = _session()
    client.post(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": "Probability"})
    later = client.get(f"/api/session/{session_id}").json()
    assert PROGRESS_REPORT_KEYS == ("study_progress", "readiness", "study_actions", "prerequisite_tree")
    for key in ("study_progress", "readiness"):  # GET /api/session does not expose study_actions
        assert later[key] == upfront[key], key


def test_known_answers_like_studied_and_fails_at_the_same_stage():
    session_id, report = _session()
    base = f"/api/prerequisites/sessions/{session_id}"
    plan = [item["concept"] for item in report["study_progress"]]
    studied = client.post(f"{base}/studied", params={"concept": plan[0]}).json()
    known = client.post(f"{base}/known", params={"concept": plan[1]}).json()
    assert set(studied) <= set(known)  # every field /studied returns is returned by /known too
    assert known["readiness"] == known["report"]["readiness"] and known["readiness"]["total_concepts"] == len(plan) - 1
    bad = [client.post(f"{base}/{kind}", params={"concept": "Cooking"}).json() for kind in ("studied", "known")]
    assert bad[0]["stage"] == bad[1]["stage"] == "study_progress"
