"""An unusable PREREQAI_MAX_ANALYSIS_SECONDS still means no limit, but the analysis says so instead of hiding the typo."""
import pytest
from starlette.testclient import TestClient

from backend.main import app


def _warnings():
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        response = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")})
    assert response.status_code == 200
    return response.json()["warnings"]


@pytest.mark.parametrize("value", ["abc", "0", "-5", "nan", "inf"])
def test_unusable_limit_is_reported_in_warnings(monkeypatch, value):
    monkeypatch.setenv("PREREQAI_MAX_ANALYSIS_SECONDS", value)
    assert any(f"PREREQAI_MAX_ANALYSIS_SECONDS='{value}' is not a positive number" in w for w in _warnings())


@pytest.mark.parametrize("value", [None, "", "   ", "600"])
def test_unset_blank_or_valid_limit_adds_no_warning(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PREREQAI_MAX_ANALYSIS_SECONDS", raising=False)
    else:
        monkeypatch.setenv("PREREQAI_MAX_ANALYSIS_SECONDS", value)
    assert _warnings() == []
