import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.cli import main
from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
client = TestClient(app)


def _plan(report):
    return [step["concept"] for step in report["learning_plan"]]


def test_known_concepts_leave_the_plan_through_the_api():
    with SAMPLE.open("rb") as f:
        base = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", f, "application/pdf")}).json()["report"]
    skip = _plan(base)[0]
    with SAMPLE.open("rb") as f:
        out = client.post("/api/prerequisites/analyze", data={"known": [skip.lower()]},
                          files={"paper": ("p.pdf", f, "application/pdf")}).json()["report"]
    assert skip not in _plan(out) and len(_plan(out)) == len(_plan(base)) - 1
    assert skip not in [p["concept"] for p in out["study_progress"]]
    assert out["study_time"]["total_hours"] < base["study_time"]["total_hours"]
    assert out["readiness"]["total_concepts"] == base["readiness"]["total_concepts"] - 1


def test_known_flag_on_the_cli_and_no_flag_is_unchanged(capsys):
    assert main(["prerequisites", "analyze", str(SAMPLE), "--json"]) == 0
    base = json.loads(capsys.readouterr().out)["report"]
    skip = _plan(base)[0]
    assert main(["prerequisites", "analyze", str(SAMPLE), "--json", "--known", skip]) == 0
    assert skip not in _plan(json.loads(capsys.readouterr().out)["report"])
