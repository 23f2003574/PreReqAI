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


# ---- the counters are shared by every worker process --------------------------------------------------------------------------------------------------------------

import json as _json
import multiprocessing as _mp
import os as _os


def _fail_many(directory, client, times, barrier):
    _os.environ[api_auth.DIR_ENV] = directory
    _os.environ[api_auth.MAX_FAILURES_ENV] = "1000"
    barrier.wait(30)
    for _ in range(times):
        api_auth.record_failure(client)


def _wait_of(directory, client, results):
    _os.environ[api_auth.DIR_ENV] = directory
    _os.environ[api_auth.MAX_FAILURES_ENV] = "10"
    results.put(api_auth.retry_after(client))


def test_concurrent_failures_in_several_processes_are_all_counted_and_the_limit_is_global(tmp_path, monkeypatch):
    pytest.importorskip("fcntl")
    directory = str(tmp_path / "auth")
    monkeypatch.setenv(api_auth.DIR_ENV, directory)
    context = _mp.get_context("spawn")
    barrier = context.Barrier(4)
    workers = [context.Process(target=_fail_many, args=(directory, "203.0.113.9", 3, barrier)) for _ in range(4)]  # four workers, three wrong tokens each: twelve in all, none above the per-process limit of ten
    for process in workers:
        process.start()
    for process in workers:
        process.join(60)
        assert process.exitcode == 0
    stored = _json.loads((tmp_path / "auth" / "auth-failures.json").read_text())
    assert [entry[0] for entry in stored.values()] == [12]  # exactly one record, no failure lost to a race
    results = context.Queue()
    other = context.Process(target=_wait_of, args=(directory, "203.0.113.9", results))
    other.start()
    other.join(60)
    assert results.get(timeout=10) >= 1  # a thirteenth worker process refuses at once: ten failures anywhere are enough
    stranger = context.Process(target=_wait_of, args=(directory, "198.51.100.1", results))
    stranger.start()
    stranger.join(60)
    assert results.get(timeout=10) == 0


def test_the_shared_file_holds_no_address_or_token_expires_and_stays_bounded(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(api_auth, "_clock", lambda: now[0])
    monkeypatch.setenv(api_auth.DIR_ENV, str(tmp_path))
    monkeypatch.setenv(api_auth.MAX_FAILURES_ENV, "2")
    monkeypatch.setenv(api_auth.WINDOW_ENV, "30")
    for number in range(api_auth.MAX_CLIENTS + 40):
        api_auth.record_failure(f"10.0.{number // 250}.{number % 250}")
    text = (tmp_path / "auth-failures.json").read_text()
    assert len(_json.loads(text)) <= api_auth.MAX_CLIENTS and "10.0." not in text and TOKEN not in text
    api_auth.record_failure("192.0.2.1"), api_auth.record_failure("192.0.2.1")
    assert api_auth.retry_after("192.0.2.1") >= 1
    now[0] += 31  # the window ended: the record is dropped from the file on the next use
    assert api_auth.retry_after("192.0.2.1") == 0 and _json.loads((tmp_path / "auth-failures.json").read_text()) == {}


def test_a_success_clears_the_shared_record_and_a_damaged_file_is_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv(api_auth.DIR_ENV, str(tmp_path))
    monkeypatch.setenv(api_auth.MAX_FAILURES_ENV, "2")
    api_auth.record_failure("192.0.2.7"), api_auth.record_failure("192.0.2.7")
    assert api_auth.retry_after("192.0.2.7") >= 1
    api_auth.record_success("192.0.2.7")
    assert api_auth.retry_after("192.0.2.7") == 0
    (tmp_path / "auth-failures.json").write_text("{not json")
    api_auth.record_failure("192.0.2.7")
    assert [entry[0] for entry in _json.loads((tmp_path / "auth-failures.json").read_text()).values()] == [1]
