"""Repeated wrong bearer tokens from one address are refused with 429 and Retry-After, then allowed again; the counters stay bounded and never hold a token."""
import pytest
from fastapi.testclient import TestClient

from backend import api_auth
from backend.main import app

pytestmark = pytest.mark.prereqai
TOKEN = "s3cret-token-VALUE-4711"
client = TestClient(app, raise_server_exceptions=False)


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def throttled(monkeypatch):
    clock = Clock()
    monkeypatch.setenv(api_auth.TOKEN_ENV, TOKEN)
    monkeypatch.setenv(api_auth.MAX_FAILURES_ENV, "3")
    monkeypatch.setenv(api_auth.WINDOW_ENV, "60")
    monkeypatch.setattr(api_auth, "_clock", clock)
    api_auth._failures.clear()
    yield clock
    api_auth._failures.clear()


def bad(value="wrong"):
    return client.get("/api/session", headers={"Authorization": f"Bearer {value}"})


def test_the_fourth_wrong_token_is_throttled_even_if_it_is_correct(throttled):
    assert [bad().status_code for _ in range(3)] == [403, 403, 403]
    refused = bad(TOKEN)
    assert refused.status_code == 429 and refused.headers["retry-after"] == "60"
    assert TOKEN not in refused.text and "wrong" not in refused.text


def test_retry_after_counts_down_and_the_window_expires(throttled):
    for _ in range(3):
        bad()
    throttled.now += 45
    assert bad().status_code == 429 and bad().headers["retry-after"] == "15"
    throttled.now += 15
    assert bad(TOKEN).status_code == 200
    assert bad().status_code == 403  # counting starts again from one


def test_a_success_clears_earlier_failures(throttled):
    bad(), bad()
    assert bad(TOKEN).status_code == 200
    assert [bad().status_code for _ in range(3)] == [403, 403, 403]


def test_a_missing_credential_is_not_counted_and_health_stays_open(throttled):
    for _ in range(6):
        assert client.get("/api/session").status_code == 401
    assert client.get("/health").status_code == 200
    for _ in range(3):
        bad()
    assert client.get("/health").status_code == 200


def test_another_address_is_not_throttled(throttled):
    for _ in range(3):
        bad()
    assert api_auth.retry_after("203.0.113.9") == 0 and api_auth.retry_after("testclient") > 0


def test_the_table_of_failing_addresses_is_bounded_and_holds_no_token(throttled):
    for number in range(api_auth.MAX_CLIENTS + 50):
        api_auth.record_failure(f"198.51.100.{number}")
    assert len(api_auth._failures) <= api_auth.MAX_CLIENTS
    assert all(isinstance(key, str) and TOKEN not in key for key in api_auth._failures)


def test_without_a_token_configured_nothing_is_throttled(monkeypatch):
    monkeypatch.delenv(api_auth.TOKEN_ENV, raising=False)
    api_auth._failures.clear()
    assert all(bad().status_code == 200 for _ in range(15))
