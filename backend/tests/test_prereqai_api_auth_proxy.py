"""Behind a trusted reverse proxy the throttle counts the client the proxy saw, not the proxy; without the setting a forged header changes nothing."""
import pytest
from fastapi.testclient import TestClient

from backend import api_auth
from backend.main import app

pytestmark = pytest.mark.prereqai
TOKEN = "s3cret-token-VALUE-4711"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv(api_auth.TOKEN_ENV, TOKEN)
    monkeypatch.setenv(api_auth.MAX_FAILURES_ENV, "2")
    api_auth._failures.clear()
    yield
    api_auth._failures.clear()


def get(token, forwarded=None):
    headers = {"Authorization": f"Bearer {token}", **({"X-Forwarded-For": forwarded} if forwarded else {})}
    return client.get("/api/session", headers=headers).status_code


def test_without_the_setting_the_forwarded_header_is_ignored_so_it_cannot_dodge_the_throttle():
    assert [get("bad", f"198.51.100.{n}") for n in range(3)] == [403, 403, 429]


def test_with_the_setting_each_forwarded_client_is_counted_separately(monkeypatch):
    monkeypatch.setenv(api_auth.PROXY_ENV, "1")
    assert [get("bad", "198.51.100.1") for _ in range(2)] == [403, 403]
    assert get("bad", "198.51.100.1") == 429
    assert get(TOKEN, "198.51.100.2") == 200  # another learner behind the same proxy is not locked out


def test_the_last_entry_is_used_because_the_proxy_appends_it(monkeypatch):
    monkeypatch.setenv(api_auth.PROXY_ENV, "1")
    for guess in ("1.1.1.1", "2.2.2.2"):  # a client writing its own leading entries gains nothing
        get("bad", f"{guess}, 203.0.113.7")
    assert get("bad", "3.3.3.3, 203.0.113.7") == 429


def test_a_missing_or_empty_header_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv(api_auth.PROXY_ENV, "true")
    assert api_auth.client_address({"client": ("10.0.0.9", 1), "headers": []}) == "10.0.0.9"
    assert api_auth.client_address({"client": ("10.0.0.9", 1), "headers": [(b"x-forwarded-for", b" ")]}) == "10.0.0.9"
    assert api_auth.client_address({"headers": []}) == "unknown"
