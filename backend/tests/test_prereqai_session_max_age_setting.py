"""An unusable PREREQAI_SESSION_MAX_AGE_DAYS (a typo such as "7d", NaN, a negative number) still falls back to the 30-day
default, but the analysis now says so in its `warnings`, as it already does for PREREQAI_MAX_ANALYSIS_SECONDS."""
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai


def _warnings(client):
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")})
    assert response.status_code == 200
    return response.json()["warnings"]


@pytest.mark.parametrize("value", ["7d", "nan", "-3", "soon"])
def test_an_unusable_setting_is_reported_and_the_default_still_applies(tmp_path, monkeypatch, value):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", value)

    warnings = _warnings(TestClient(app))

    assert any(f"PREREQAI_SESSION_MAX_AGE_DAYS={value!r}" in w and "default of 30 days" in w for w in warnings)
    assert SessionManager._max_age_seconds() == 30 * 86400  # unchanged compatibility: the default still applies


@pytest.mark.parametrize("value", [None, "", "  ", "7", "0.5", "0", "inf"])
def test_valid_unset_or_blank_settings_add_no_warning(tmp_path, monkeypatch, value):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    if value is None:
        monkeypatch.delenv("PREREQAI_SESSION_MAX_AGE_DAYS", raising=False)
    else:
        monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", value)

    assert not any("MAX_AGE_DAYS" in w for w in _warnings(TestClient(app)))


def test_without_a_session_directory_the_setting_is_irrelevant_and_silent(monkeypatch):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", "7d")

    assert not any("MAX_AGE_DAYS" in w for w in _warnings(TestClient(app)))
