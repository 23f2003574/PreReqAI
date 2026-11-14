"""A version-3 session saved before MissingPrerequisite.sections existed loads and rebuilds its report (compatibility repair)."""
import pickle

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)


def test_a_version_3_session_without_sections_loads_and_its_report_is_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    sid = platform.analyze(SAMPLE)["session_id"]
    path = tmp_path / f"{sid}.session"
    legacy = session_manager.get(sid)
    assert legacy.paper.missing_prerequisites
    for item in legacy.paper.missing_prerequisites:  # what a file saved before 1e01b49 holds: no `sections` attribute at all
        item.__dict__.pop("sections")
    legacy.schema_version = 3
    path.write_bytes(pickle.dumps(legacy))
    session_manager.sessions.clear()

    assert SessionManager.SCHEMA_VERSION >= 3
    restored = session_manager.get(sid)  # the version equals the one the file claims, so no upgrade step used to run
    assert restored is not None and all(item.sections == [] for item in restored.paper.missing_prerequisites)
    concept = restored.paper.learning_plan[0].concept
    answer = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": concept})  # rebuilds the report from the paper
    assert answer.status_code == 200 and answer.json()["status"] == "success"
    report = client.get(f"/api/session/{sid}").json()
    assert report["readiness"]["completed_concepts"] == 1
    session_manager.sessions.clear()
