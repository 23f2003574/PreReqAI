"""GET /api/session/{id}/plan: the OpenAPI document declares what the endpoint really returns (Markdown, not JSON)."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

client = TestClient(app)


def test_openapi_declares_the_plan_as_markdown_and_not_json():
    ok = client.get("/openapi.json").json()["paths"]["/api/session/{session_id}/plan"]["get"]["responses"]["200"]["content"]
    assert list(ok) == ["text/markdown"] and ok["text/markdown"]["schema"] == {"type": "string"}


def test_the_declared_type_is_the_one_actually_served_and_failures_stay_json():
    with open("examples/prerequisites/sample-paper.pdf", "rb") as pdf:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", pdf, "application/pdf")}).json()["session_id"]
    reply = client.get(f"/api/session/{sid}/plan")
    assert reply.status_code == 200 and reply.headers["content-type"] == "text/markdown; charset=utf-8"
    assert reply.text.startswith("# Study plan: ")

    missing = client.get("/api/session/00000000-0000-0000-0000-000000000000/plan")
    assert missing.status_code == 404 and missing.headers["content-type"].startswith("application/json")
    assert missing.json()["status"] == "failure"
    assert "application/json" in client.get("/openapi.json").json()["paths"]["/api/session/{session_id}/plan"]["get"]["responses"]["404"]["content"]
