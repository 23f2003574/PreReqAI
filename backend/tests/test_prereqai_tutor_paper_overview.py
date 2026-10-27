"""Paper-level questions phrased with 'use' or 'about' get an answer from the detected concepts instead of the placeholder."""
from starlette.testclient import TestClient

from backend.main import app


def _ask(question):
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    return client.post(f"/api/session/{sid}/question", json={"question": question}).json()["responses"][0]["answer"]


def test_which_concepts_does_the_paper_use():
    assert _ask("Which concepts does this paper use?").startswith("The paper discusses these concepts, most mentioned first: Attention (4x)")


def test_what_is_the_paper_about_names_the_most_mentioned_concepts():
    answer = _ask("What is the paper about?")
    assert answer == ("Attention Is All You Need (PreReqAI sample paper) is mostly about: Attention, Softmax, Gradient Descent "
                      "(the concepts it mentions most).")


def test_study_questions_with_the_word_concepts_still_get_the_study_plan():
    assert _ask("Which concepts do I need to study first?").startswith("Study these in order before the paper")
