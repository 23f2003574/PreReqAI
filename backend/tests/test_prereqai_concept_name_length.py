"""An oversized `known` / `studied` name is refused at the HTTP boundary instead of being analysed and echoed back in a warning."""
import pytest
from fastapi.testclient import TestClient

from backend.api.prerequisite_routes import MAX_CONCEPT_NAME_CHARS
from backend.main import app

pytestmark = pytest.mark.prereqai

client = TestClient(app)
PDF = open("examples/prerequisites/sample-paper.pdf", "rb").read()


def _analyze(**data):
    return client.post("/api/prerequisites/analyze", files={"paper": ("a.pdf", PDF, "application/pdf")}, data=data)


@pytest.mark.parametrize("field", ["known", "studied"])
def test_an_oversized_name_is_refused_with_a_422_and_nothing_is_analysed(field):
    response = _analyze(**{field: ["Calculus", "a" * (MAX_CONCEPT_NAME_CHARS + 1)]})
    body = response.json()
    assert response.status_code == 422 and body["stage"] == "input" and "session_id" not in body
    assert "a" * 50 not in str(body)  # the oversized value is not echoed back


def test_names_up_to_the_limit_still_work_and_an_unknown_one_is_just_a_warning():
    response = _analyze(known=["Calculus", "a" * MAX_CONCEPT_NAME_CHARS])
    body = response.json()
    assert response.status_code == 200 and body["status"] == "success"
    assert any("is not in this paper's study plan" in warning for warning in body["warnings"])
