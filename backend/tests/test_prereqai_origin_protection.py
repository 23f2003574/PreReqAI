"""The local server refuses DNS-rebinding Hosts, cross-site state-changing requests and wrong content types, and sends security headers."""
import json
import re

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.security import host_allowed

pytestmark = pytest.mark.prereqai
JSON = {"Content-Type": "application/json"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    monkeypatch.delenv("PREREQAI_TRUSTED_HOSTS", raising=False)
    monkeypatch.delenv("PREREQAI_CORS_ORIGINS", raising=False)
    return TestClient(main.app, base_url="http://localhost:8000")


def test_host_parsing():
    for good in ("localhost", "localhost:8000", "127.0.0.1:9", "[::1]:8000", "[::1]", "LOCALHOST"):
        assert host_allowed(good), good
    for bad in ("", "evil.example", "evil.example:8000", "localhost.evil.example", "127.0.0.1.evil.example", "localhost,evil.example", "[::2]:80"):
        assert not host_allowed(bad), bad


def test_rebinding_host_is_refused_and_trusted_hosts_work(client, monkeypatch):
    refused = client.get("/health", headers={"Host": "attacker.example:8000"})
    assert refused.status_code == 403 and refused.json()["status"] == "failure"
    assert client.get("/health", headers={"Host": "localhost:8000"}).status_code == 200
    assert client.get("/health", headers={"Host": "127.0.0.1:1"}).status_code == 200
    monkeypatch.setenv("PREREQAI_TRUSTED_HOSTS", "prereqai.internal, proxy.example:8443")
    assert client.get("/health", headers={"Host": "prereqai.internal"}).status_code == 200
    assert client.get("/health", headers={"Host": "proxy.example:8443"}).status_code == 200
    assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 403


def test_forwarded_headers_are_not_trusted(client):
    forwarded = {"X-Forwarded-Host": "localhost", "Forwarded": "host=localhost", "X-Original-Host": "localhost"}
    assert client.get("/health", headers={"Host": "attacker.example", **forwarded}).status_code == 403


def test_cross_site_profile_import_is_refused_and_changes_nothing(client):
    client.post("/api/profiles/me/import", headers=JSON, content=json.dumps({"schema_version": 2, "profile": "me", "known_concepts": ["attention"]}))
    before = client.get("/api/profiles/me/export").content
    for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}, {"Origin": "http://localhost:9999"}):
        attack = client.post("/api/profiles/me/import", params={"replace": "true"}, headers={**JSON, **headers}, content=b'{"schema_version": 2, "profile": "me"}')
        assert attack.status_code == 403, headers
    assert client.get("/api/profiles/me/export").content == before


def test_same_origin_and_command_line_requests_work(client):
    body = client.get("/api/profiles/me/export")
    payload = body.content if body.status_code == 200 else json.dumps({"schema_version": 2, "profile": "me"})
    same = client.post("/api/profiles/same/import", headers={**JSON, "Origin": "http://localhost:8000", "Sec-Fetch-Site": "same-origin"}, content=payload)
    plain = client.post("/api/profiles/plain/import", headers=JSON, content=payload)  # no Origin: curl, the CLI, tests
    assert same.status_code != 403 and plain.status_code != 403, (same.text, plain.text)


def test_configured_cors_origin_may_change_data(client, monkeypatch):
    monkeypatch.setenv("PREREQAI_CORS_ORIGINS", "https://app.example.com")
    response = client.post("/api/profiles/x/import", headers={**JSON, "Origin": "https://app.example.com"}, content=b"{}")
    assert response.status_code != 403


def test_content_types(client):
    assert client.post("/api/profiles/x/import", headers={"Content-Type": "text/plain"}, content=b"{}").status_code == 415  # the no-preflight cross-site form
    assert client.post("/api/profiles/x/import", content=b"{}").status_code == 415
    assert client.post("/api/profiles/x/import", headers={"Content-Type": "multipart/form-data; boundary=x"}, content=b"--x--").status_code == 415
    assert client.post("/api/profiles/x/import", headers=JSON, content=b"{not json").status_code == 422
    assert client.post("/api/sessions", headers={"Content-Type": "text/plain"}, content=b"hello").status_code == 415


def test_security_headers_and_csp_nonce(client):
    page = client.get("/")
    assert page.headers["x-content-type-options"] == "nosniff" and page.headers["x-frame-options"] == "DENY"
    csp = page.headers["content-security-policy"]
    nonce = re.search(r"nonce-([\w-]+)", csp).group(1)
    assert f'<script nonce="{nonce}">' in page.text and "frame-ancestors 'none'" in csp
    other = client.get("/").headers["content-security-policy"]
    assert other != csp  # a fresh nonce for every response
    assert "content-security-policy" not in client.get("/docs").headers
    assert client.get("/health").headers["x-content-type-options"] == "nosniff"
