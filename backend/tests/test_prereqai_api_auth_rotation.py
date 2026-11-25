"""A second token can be accepted while the first is being replaced, so the token rotates without downtime."""
import pytest
from fastapi.testclient import TestClient

from backend import api_auth
from backend.main import app

pytestmark = pytest.mark.prereqai
OLD, NEW = "old-token-VALUE-1111", "new-token-VALUE-2222"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    api_auth._failures.clear()
    monkeypatch.delenv(api_auth.NEXT_TOKEN_ENV, raising=False)
    yield
    api_auth._failures.clear()


def status(token):
    return client.get("/api/session", headers={"Authorization": f"Bearer {token}"}).status_code


def test_both_tokens_are_accepted_during_a_rotation_and_others_are_not(monkeypatch):
    monkeypatch.setenv(api_auth.TOKEN_ENV, OLD)
    monkeypatch.setenv(api_auth.NEXT_TOKEN_ENV, NEW)
    assert status(OLD) == 200 and status(NEW) == 200 and status("third") == 403


def test_after_the_rotation_the_old_token_stops_working(monkeypatch):
    monkeypatch.setenv(api_auth.TOKEN_ENV, NEW)
    assert status(NEW) == 200 and status(OLD) == 403


def test_the_next_token_alone_turns_authentication_on_and_blank_values_are_ignored(monkeypatch):
    monkeypatch.delenv(api_auth.TOKEN_ENV, raising=False)
    monkeypatch.setenv(api_auth.NEXT_TOKEN_ENV, NEW)
    assert client.get("/api/session").status_code == 401 and status(NEW) == 200
    monkeypatch.setenv(api_auth.NEXT_TOKEN_ENV, "   ")
    assert client.get("/api/session").status_code == 200  # nothing configured: off, as before
    assert api_auth.configured_tokens() == []


def test_the_exposure_warning_counts_the_next_token_and_the_helpers_still_take_one_token(monkeypatch):
    monkeypatch.delenv(api_auth.TOKEN_ENV, raising=False)
    monkeypatch.setenv(api_auth.NEXT_TOKEN_ENV, NEW)
    assert api_auth.warn_if_exposed(["--host", "0.0.0.0"], {}) is None
    assert api_auth.check(f"Bearer {NEW}", NEW) is None and api_auth.check(f"Bearer {OLD}", [NEW, OLD]) is None
