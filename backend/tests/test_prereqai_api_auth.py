"""Optional bearer-token authentication: correct token succeeds, none is 401, a wrong one 403, /health and the page stay open, nothing leaks the token, and an exposed server without a token warns."""
import logging

import pytest
from fastapi.testclient import TestClient

from backend import api_auth
from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
TOKEN = "s3cret-token-VALUE-4711"
client = TestClient(app, raise_server_exceptions=False)
SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture
def secured(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv(api_auth.TOKEN_ENV, TOKEN)
    session_manager.sessions.clear()
    yield
    session_manager.sessions.clear()


def bearer(value):
    return {"Authorization": f"Bearer {value}"}


def test_without_a_configured_token_nothing_changes(monkeypatch):
    monkeypatch.delenv(api_auth.TOKEN_ENV, raising=False)
    assert client.get("/api/session").status_code == 200
    monkeypatch.setenv(api_auth.TOKEN_ENV, "   ")  # blank is the same as unset
    assert client.get("/api/session").status_code == 200


def test_session_listing_needs_the_token(secured):
    assert client.get("/api/session").status_code == 401
    assert client.get("/api/session").headers["www-authenticate"] == "Bearer"
    assert client.get("/api/session", headers=bearer("wrong")).status_code == 403
    assert client.get("/api/session", headers={"Authorization": f"Basic {TOKEN}"}).status_code == 403
    assert client.get("/api/session", headers={"Authorization": "Bearer "}).status_code == 403
    response = client.get("/api/session", headers=bearer(TOKEN))
    assert response.status_code == 200 and response.json()["status"] == "success"


def test_session_access_and_destructive_endpoints_are_protected(secured):
    for method, path in (("get", "/api/session/abc"), ("delete", "/api/session/abc"), ("get", "/api/profiles"), ("post", "/api/prerequisites/analyze"), ("delete", "/api/profiles/me")):
        assert getattr(client, method)(path).status_code == 401, path
        assert getattr(client, method)(path, headers=bearer("nope")).status_code == 403, path
    assert client.delete("/api/session/abc", headers=bearer(TOKEN)).status_code == 404  # authorised: the request reaches the route (no such session)
    with open(SAMPLE, "rb") as handle:
        refused = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")})
    assert refused.status_code == 401
    with open(SAMPLE, "rb") as handle:
        accepted = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, headers=bearer(TOKEN))
    assert accepted.status_code == 200 and accepted.json()["status"] == "success"


def test_health_the_page_and_the_docs_stay_open(secured):
    assert client.get("/health").status_code == 200
    page = client.get("/")
    assert page.status_code == 200 and TOKEN not in page.text and "PREREQAI_API_TOKEN" in page.text
    assert client.get("/docs").status_code == 200


def test_the_token_is_never_echoed_or_logged(secured, caplog):
    with caplog.at_level(logging.DEBUG):
        for headers in ({}, bearer("wrong"), bearer(TOKEN[:-1]), bearer(TOKEN)):
            response = client.get("/api/session", headers=headers)
            assert TOKEN not in response.text and TOKEN not in str(response.headers)
    assert TOKEN not in caplog.text and "wrong" not in caplog.text


def test_the_comparison_is_constant_time_and_exact(secured, monkeypatch):
    calls = []
    real = api_auth.hmac.compare_digest
    monkeypatch.setattr(api_auth.hmac, "compare_digest", lambda a, b: calls.append((len(a), len(b))) or real(a, b))
    assert client.get("/api/session", headers=bearer(TOKEN + "x")).status_code == 403 and client.get("/api/session", headers=bearer(TOKEN.upper())).status_code == 403
    assert len(calls) == 2
    assert api_auth.check(f"bearer {TOKEN}", TOKEN) is None  # the scheme name is case-insensitive, the token is not


@pytest.mark.parametrize("argv,environ,host", [(["uvicorn", "backend.main:app", "--host", "0.0.0.0"], {}, "0.0.0.0"), (["uvicorn", "--host=192.168.1.5"], {}, "192.168.1.5"), (["uvicorn"], {"UVICORN_HOST": "::"}, "::"), (["uvicorn"], {}, None)])
def test_the_requested_listening_address_is_found(argv, environ, host):
    assert api_auth.bind_host(argv, environ) == host


def test_an_exposed_server_without_a_token_warns_and_a_loopback_or_secured_one_does_not(monkeypatch, caplog):
    monkeypatch.delenv(api_auth.TOKEN_ENV, raising=False)
    with caplog.at_level(logging.WARNING, logger="prereqai.security"):
        message = api_auth.warn_if_exposed(["uvicorn", "--host", "0.0.0.0"], {})
    assert message and "0.0.0.0" in message and api_auth.TOKEN_ENV in message and message in caplog.text
    assert api_auth.warn_if_exposed(["uvicorn", "--host", "127.0.0.1"], {}) is None and api_auth.warn_if_exposed(["uvicorn"], {}) is None
    monkeypatch.setenv(api_auth.TOKEN_ENV, TOKEN)
    caplog.clear()
    assert api_auth.warn_if_exposed(["uvicorn", "--host", "0.0.0.0"], {}) is None and not caplog.records
