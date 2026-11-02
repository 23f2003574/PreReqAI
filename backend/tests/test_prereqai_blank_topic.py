"""A blank `topic` over HTTP is refused with a hint, like a blank --topic on the command line, instead of being ignored."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai


@pytest.fixture()
def session():
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as pdf:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", pdf, "application/pdf")}).json()["session_id"]
    return client, f"/api/session/{sid}/question"


@pytest.mark.parametrize("topic", ["", "   ", "\t"])
def test_a_blank_topic_is_rejected_with_an_actionable_hint(session, topic):
    client, url = session
    reply = client.post(url, json={"question": "What is attention?", "topic": topic})
    assert reply.status_code == 422
    body = reply.json()
    assert body["stage"] == "question" and "blank" in body["hint"] and "omit `topic`" in body["hint"]


@pytest.mark.parametrize("payload", [{"question": "What is attention?"}, {"question": "What is attention?", "topic": None},
                                     {"question": "What is attention?", "topic": " softmax "}])
def test_no_topic_null_topic_and_a_padded_real_topic_still_work(session, payload):
    client, url = session
    assert client.post(url, json=payload).status_code == 200
