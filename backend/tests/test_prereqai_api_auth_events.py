"""Refused and throttled API requests are structured events an operator can count, and they never carry the token or the address."""
import logging

import pytest
from fastapi.testclient import TestClient

from backend import api_auth, observability
from backend.main import app

pytestmark = pytest.mark.prereqai
TOKEN, GUESS = "s3cret-token-VALUE-4711", "guess-VALUE-9999"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def records(caplog, monkeypatch):
    monkeypatch.setenv(api_auth.TOKEN_ENV, TOKEN)
    monkeypatch.setenv(api_auth.MAX_FAILURES_ENV, "2")
    api_auth._failures.clear()
    caplog.set_level(logging.INFO, logger=observability.EVENT_LOGGER)
    yield lambda name: [r.fields for r in caplog.records if r.name == observability.EVENT_LOGGER and r.fields["event"] == name]
    api_auth._failures.clear()


def test_refusals_and_throttling_are_events_without_secrets(records, caplog):
    client.get("/api/session")
    client.get("/api/session", headers={"Authorization": f"Bearer {GUESS}"})
    client.get("/api/session", headers={"Authorization": f"Bearer {GUESS}"})
    client.get("/api/session", headers={"Authorization": f"Bearer {TOKEN}"})
    refused = records("auth_refused")
    assert [(r["status"], r["credential_sent"]) for r in refused] == [(401, False), (403, True), (403, True)]
    throttled = records("auth_throttled")
    assert len(throttled) == 1 and throttled[0]["retry_after_seconds"] >= 1
    everything = " ".join(r.getMessage() for r in caplog.records)
    assert TOKEN not in everything and GUESS not in everything and "testclient" not in everything


def test_a_successful_request_logs_no_auth_event(records):
    client.get("/api/session", headers={"Authorization": f"Bearer {TOKEN}"})
    assert records("auth_refused") == [] and records("auth_throttled") == []
