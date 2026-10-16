import importlib

from fastapi.testclient import TestClient

import backend.main as main

PREFLIGHT = {"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST"}


def _client(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PREREQAI_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("PREREQAI_CORS_ORIGINS", value)
    return TestClient(importlib.reload(main).app)


def test_cors_is_off_by_default_and_for_blank_values(monkeypatch):
    for value in (None, "", " , "):
        assert "access-control-allow-origin" not in _client(monkeypatch, value).options("/health", headers=PREFLIGHT).headers
    _client(monkeypatch, None)  # leave the module as a default import


def test_listed_origins_are_allowed_others_are_not(monkeypatch):
    client = _client(monkeypatch, "https://app.example.com/, https://other.example.com")
    assert client.options("/health", headers=PREFLIGHT).headers["access-control-allow-origin"] == "https://app.example.com"
    assert client.get("/health", headers={"Origin": "https://app.example.com"}).headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" not in client.get("/health", headers={"Origin": "https://evil.example"}).headers
    _client(monkeypatch, None)
