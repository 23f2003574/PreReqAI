"""The readings, evidence and curriculum commands give the same data as the API for the same saved sessions, and fail clearly."""
import json

import pytest
from fastapi.testclient import TestClient

from backend import learner_profile
from backend.cli import main
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    directory = tmp_path_factory.mktemp("sessions")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PREREQAI_SESSION_DIR", str(directory))
        session_manager.sessions.clear()
        ids = {name: platform.analyze(path)["session_id"] for name, path in (("sample", "examples/prerequisites/sample-paper.pdf"), ("mixtral", "backend/prereqai_eval/benchmark/pdfs/mixtral.pdf"))}
        session_manager.sessions.clear()
    return directory, ids


@pytest.fixture
def env(saved, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(saved[0]))
    session_manager.sessions.clear()
    yield saved[1]
    session_manager.sessions.clear()


def cli_json(capsys, *argv):
    code = main(["prerequisites", *argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_readings_match_the_api(env, capsys):
    api = client.get(f"/api/session/{env['mixtral']}/reading-list", params={"limit": 5}).json()
    code, cli = cli_json(capsys, "readings", env["mixtral"], "--limit", "5")
    assert code == 0 and cli == api and len(cli["reading_list"]) == 5
    assert main(["prerequisites", "readings", env["mixtral"], "--limit", "2"]) == 0
    text = capsys.readouterr().out
    assert text.count("\n#") + text.startswith("#") == 2 and "read next with:" in text


def test_evidence_matches_the_api_and_can_be_limited_to_a_concept(env, capsys):
    api = client.get(f"/api/session/{env['mixtral']}/evidence").json()
    code, cli = cli_json(capsys, "evidence", env["mixtral"])
    assert code == 0 and cli == api and api["evidence"] and api["evidence"][0]["passages"]
    api_one = client.get(f"/api/session/{env['mixtral']}/evidence", params={"concept": "mixture of experts"}).json()
    code, cli_one = cli_json(capsys, "evidence", env["mixtral"], "--concept", "Mixture of Experts")
    assert code == 0 and cli_one == api_one and [e["concept"] for e in cli_one["evidence"]] == ["Mixture of Experts"]
    assert main(["prerequisites", "evidence", env["mixtral"]]) == 0 and "[p-" in capsys.readouterr().out
    assert main(["prerequisites", "evidence", env["mixtral"], "--concept", "Astrology"]) == 2 and "not a concept detected" in capsys.readouterr().err


def test_curriculum_matches_the_api_with_a_profile_and_a_deadline(env, capsys, tmp_path, monkeypatch):
    profile = tmp_path / "profiles" / "me.json"
    learner_profile.save(profile, ["Calculus"], [])
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    ids = [env["sample"], env["mixtral"]]
    api = client.post("/api/curriculum", json={"session_ids": ids, "profile": "me", "deadline": "2099-01-01", "weekdays": "mon,tue,wed,thu,fri", "hours_per_day": 2}).json()
    code, cli = cli_json(capsys, "curriculum", *ids, "--profile", str(profile), "--deadline", "2099-01-01", "--study-days", "mon,tue,wed,thu,fri", "--hours-per-day", "2")
    assert code == 0 and cli == api and "Calculus" in [e["concept"] for e in api["excluded"]]
    assert main(["prerequisites", "curriculum", *ids, "--profile", str(profile)]) == 0
    text = capsys.readouterr().out
    assert text.startswith("Together:") and "1. " in text and "calendar:" in text


def test_missing_sessions_bad_input_and_no_session_directory_fail_clearly(env, capsys, monkeypatch):
    assert main(["prerequisites", "readings", "nope"]) == 1 and "was not found" in capsys.readouterr().err
    assert main(["prerequisites", "evidence", "nope"]) == 1 and main(["prerequisites", "curriculum", env["sample"], "nope"]) == 1
    capsys.readouterr()
    assert main(["prerequisites", "curriculum", env["sample"]]) == 2 and "2 to 10" in capsys.readouterr().err
    assert main(["prerequisites", "curriculum", env["sample"], env["sample"]]) == 2
    assert main(["prerequisites", "curriculum", env["sample"], env["mixtral"], "--deadline", "soon"]) == 2 and "--deadline" in capsys.readouterr().err
    assert main(["prerequisites", "readings", env["sample"], "--limit", "0"]) == 2
    path = learner_profile.profile_path(__import__("tempfile").mkdtemp(), "bad")
    path.write_text("{nope", encoding="utf-8")
    assert main(["prerequisites", "curriculum", env["sample"], env["mixtral"], "--profile", str(path)]) == 1 and path.read_text() == "{nope"
    monkeypatch.delenv("PREREQAI_SESSION_DIR")
    assert main(["prerequisites", "readings", env["sample"]]) == 1 and "PREREQAI_SESSION_DIR" in capsys.readouterr().err


def test_a_session_saved_before_evidence_existed_still_shows_it(env, capsys):
    session = session_manager.get(env["sample"])
    for item in session.report["concept_evidence"]:
        item.pop("passages", None)  # a report from before evidence passages
    code, cli = cli_json(capsys, "evidence", env["sample"])
    assert code == 0 and any(item["passages"] for item in cli["evidence"])  # recomputed from the paper
