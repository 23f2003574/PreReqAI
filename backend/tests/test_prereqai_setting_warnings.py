"""A limit or throttle setting that is set but unusable is reported by /health instead of silently falling back to its default."""
import pytest
from fastapi.testclient import TestClient

from backend import analysis_slots, api_auth
from backend.main import app

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)
NAMES = (analysis_slots.SLOTS_ENV, api_auth.MAX_FAILURES_ENV, api_auth.WINDOW_ENV)


@pytest.fixture(autouse=True)
def unset(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)


def test_usable_unset_or_blank_settings_give_no_warnings(monkeypatch):
    assert "warnings" not in client.get("/health").json()
    for name, value in ((NAMES[0], "3"), (NAMES[1], "5"), (NAMES[2], "12.5"), (NAMES[0], "  ")):
        monkeypatch.setenv(name, value)
    assert "warnings" not in client.get("/health").json()


@pytest.mark.parametrize("value", ["many", "0", "-2", "1.5", "2x"])
def test_an_unusable_slot_limit_is_reported_with_the_default_that_applies(monkeypatch, value):
    monkeypatch.setenv(analysis_slots.SLOTS_ENV, value)
    [warning] = client.get("/health").json()["warnings"]
    assert repr(value) in warning and str(analysis_slots.limit()) in warning


def test_unusable_throttle_settings_are_reported_each_by_name(monkeypatch):
    monkeypatch.setenv(api_auth.MAX_FAILURES_ENV, "ten")
    monkeypatch.setenv(api_auth.WINDOW_ENV, "-1")
    warnings = client.get("/health").json()["warnings"]
    assert len(warnings) == 2 and api_auth.MAX_FAILURES_ENV in warnings[0] and api_auth.WINDOW_ENV in warnings[1]
    assert "default 10" in warnings[0].replace("applies", "").replace("the ", "") or "10" in warnings[0]


def test_the_defaults_really_do_apply_when_a_setting_is_unusable(monkeypatch):
    monkeypatch.setenv(api_auth.MAX_FAILURES_ENV, "ten")
    monkeypatch.setenv(api_auth.WINDOW_ENV, "soon")
    assert api_auth._number(api_auth.MAX_FAILURES_ENV, api_auth.DEFAULT_MAX_FAILURES, whole=True) == 10
    assert api_auth._number(api_auth.WINDOW_ENV, api_auth.DEFAULT_WINDOW) == 60.0
