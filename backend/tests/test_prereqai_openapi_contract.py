"""/openapi.json -- what a generated client is built from -- lists only responses the service can really send: no 404 "Unknown
session" on routes that take no session id, and still the documented ones everywhere else."""
import pytest
from starlette.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai


def _responses(client, path, method):
    return set(client.get("/openapi.json").json()["paths"][path][method]["responses"])


def test_routes_without_a_session_do_not_advertise_unknown_session():
    client = TestClient(app)

    assert _responses(client, "/api/prerequisites/analyze", "post") == {"200", "400", "409", "413", "422", "504"}
    assert "404" not in _responses(client, "/api/session", "get")


def test_session_routes_still_document_unknown_session_and_it_is_what_they_return():
    client = TestClient(app)

    for path, method in (("/api/session/{session_id}", "get"), ("/api/session/{session_id}", "delete"),
                         ("/api/session/{session_id}/question", "post"),
                         ("/api/prerequisites/sessions/{session_id}/studied", "post")):
        assert "404" in _responses(client, path, method)

    assert client.get("/api/session/00000000-0000-4000-8000-000000000000").status_code == 404
    assert client.get("/api/session").status_code == 200
