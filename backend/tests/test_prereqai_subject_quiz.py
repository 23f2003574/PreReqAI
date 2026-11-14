"""The nine foundational prerequisite subjects can be quizzed by name through the interactive quiz; concept quizzes and refusals are unchanged."""
import pytest
from fastapi.testclient import TestClient

from backend.concepts.concept_registry import ConceptRegistry
from backend.main import app
from backend.platform import platform
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner
from backend.session import session_manager
from backend.tutor.quiz_bank import QUIZ_BANK, SUBJECT_QUIZ_BANK

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
SUBJECTS = ["Linear Algebra", "Probability", "Calculus", "Information Theory", "Optimization", "Statistics", "Stochastic Processes",
            "Neural Networks", "Graphs"]
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def test_every_foundational_subject_has_at_least_three_valid_questions():
    assert set(SUBJECTS) <= set(SUBJECT_QUIZ_BANK) and set(SUBJECT_QUIZ_BANK) <= set(PrerequisiteLearningPlanner.STUDY_TIME)
    assert not set(SUBJECT_QUIZ_BANK) & {c.name for c in ConceptRegistry().all()}  # kept apart from the registry-concept bank
    seen = set()
    for subject in SUBJECTS:
        assert len(SUBJECT_QUIZ_BANK[subject]) >= 3
        for item in SUBJECT_QUIZ_BANK[subject]:
            assert set(item) == {"question", "answer", "difficulty"} and item["difficulty"] in {"Easy", "Medium", "Hard"}
            assert item["question"].endswith("?") and item["answer"].endswith(".") and len(item["answer"].split()) >= 10
            assert item["question"] not in seen and item["question"] not in {q["question"] for v in QUIZ_BANK.values() for q in v}
            seen.add(item["question"])


@pytest.mark.parametrize("subject", SUBJECTS)
def test_each_subject_is_served_revealed_and_recorded_through_the_api(sid, subject):
    served = client.get(f"/api/session/{sid}/quiz/question", params={"concept": subject.lower()}).json()
    assert served["concept"] == subject and served["question_id"].startswith(f"{subject}:")
    assert "answer" not in served
    expected = SUBJECT_QUIZ_BANK[subject][int(served["question_id"].rpartition(":")[2]) - 1]
    assert served["question"] == expected["question"]
    revealed = client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": served["question_id"]}).json()
    assert revealed["answer"] == expected["answer"]
    done = client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": served["question_id"], "outcome": "knew"}).json()
    assert [(c["concept"], c["attempts"]) for c in done["progress"]["concepts"]] == [(subject, 1)]


def test_a_subject_rotates_through_its_questions_deterministically(sid):
    first = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Calculus"}).json()["question_id"]
    client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": first, "outcome": "missed"})
    second = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Calculus"}).json()["question_id"]
    assert (first, second) == ("Calculus:1", "Calculus:2")


def test_unsupported_topics_are_still_refused_and_the_default_pick_stays_a_paper_concept(sid):
    refused = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Astrology"})
    assert refused.status_code == 422 and refused.json()["status"] == "failure"
    default = client.get(f"/api/session/{sid}/quiz/question").json()
    assert default["concept"] in QUIZ_BANK and default["concept"] not in SUBJECT_QUIZ_BANK
    assert client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Softmax"}).json()["concept"] == "Softmax"
