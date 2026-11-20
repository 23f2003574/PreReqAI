"""Paper-specific fill-in-the-blank questions: made from verified sentences, with page and section, separate from the global questions, feeding mastery and spaced review."""
import re

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor import paper_quiz, quiz_session

pytestmark = pytest.mark.prereqai
PDFS = {name: f"backend/prereqai_eval/benchmark/pdfs/{name}.pdf" for name in ("dpo", "mixtral", "chain-of-thought")}


@pytest.fixture(scope="module")
def sessions(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PREREQAI_SESSION_DIR", str(tmp_path_factory.mktemp("sessions")))
        patch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path_factory.mktemp("profiles")))
        ids = {name: platform.analyze(path)["session_id"] for name, path in PDFS.items()}
        for sid in ids.values():  # what the analyze endpoint's `profile` field does: the session remembers its answers in this profile
            session = session_manager.get(sid)
            session.profile = "learner"
            session_manager.save(session)
        yield ids


@pytest.mark.parametrize("name", PDFS)
def test_each_benchmark_paper_has_at_least_five_questions_that_quote_the_paper_exactly(sessions, name):
    session = session_manager.get(sessions[name])
    questions = paper_quiz.build(session)
    assert len(questions) >= 5, (name, len(questions))
    pages = {page.page_number: page.text for page in session.paper.pages}
    titles = {section.title for section in session.paper.sections}
    for question in questions:
        assert question["quotation"] in pages[question["page_number"]], question["quotation"][:60]  # an exact quotation of the page it cites
        assert question["section"] in titles and question["question_id"].startswith("paper~") and ":" in question["question_id"]
        assert paper_quiz.BLANK in question["prompt"] and question["answer"].lower() in " ".join(question["quotation"].lower().split())
        assert not re.search(rf"(?<![A-Za-z0-9]){re.escape(question['answer'])}(?![A-Za-z0-9])", question["prompt"], re.IGNORECASE), "the answer must not stay in the prompt"
    assert len({q["question_id"] for q in questions}) == len(questions)


def test_a_served_question_never_carries_its_answer_and_global_questions_stay_apart(sessions):
    client = TestClient(app)
    base = f"/api/session/{sessions['dpo']}"
    body = client.get(f"{base}/paper-quiz").json()
    assert body["status"] == "success" and len(body["questions"]) >= 5
    assert all({"answer", "quotation"}.isdisjoint(q) and q["kind"] == "paper" for q in body["questions"])
    served = client.get(f"{base}/quiz/question").json()
    assert not served["question_id"].startswith("paper~") and quiz_session.ASKABLE.get(served["concept"])  # the global quiz is unchanged
    assert client.post(f"{base}/quiz/reveal", json={"question_id": body["questions"][0]["question_id"]}).status_code == 404  # and cannot serve a paper question


def test_reveal_compares_the_attempt_and_outcome_feeds_mastery_and_the_profile_review_queue(sessions):
    client = TestClient(app)
    base = f"/api/session/{sessions['mixtral']}"
    first = client.get(f"{base}/paper-quiz").json()["questions"][0]
    assert client.post(f"{base}/paper-quiz/outcome", json={"question_id": first["question_id"], "outcome": "knew"}).status_code == 409  # reveal first
    answer = next(q for q in paper_quiz.build(session_manager.get(sessions["mixtral"])) if q["question_id"] == first["question_id"])["answer"]
    wrong = client.post(f"{base}/paper-quiz/reveal", json={"question_id": first["question_id"], "attempt": "zebra"}).json()
    assert wrong["answer"] == answer and wrong["attempt_correct"] is False and wrong["page_number"] and wrong["section"] and wrong["quotation"]
    right = client.post(f"{base}/paper-quiz/reveal", json={"question_id": first["question_id"], "attempt": answer.upper()}).json()
    assert right["attempt_correct"] is True
    recorded = client.post(f"{base}/paper-quiz/outcome", json={"question_id": first["question_id"], "outcome": "missed"}).json()
    entry = next(c for c in recorded["progress"]["concepts"] if c["concept"] == first["concept"])
    assert entry["attempts"] >= 1 and entry["missed"] >= 1 and recorded["review"]["saved"] is True and recorded["review"]["question_id"] == first["question_id"]
    assert client.post(f"{base}/paper-quiz/outcome", json={"question_id": first["question_id"], "outcome": "missed"}).status_code == 409  # one outcome per question
    queue = client.get("/api/review", params={"profile": "learner"}).json()
    assert any(item["question_id"] == first["question_id"] for item in [*queue["due"], *queue["upcoming"]])
    assert client.post(f"{base}/paper-quiz/outcome", json={"question_id": "paper~p-nope:1", "outcome": "knew"}).status_code == 404
    assert client.post(f"{base}/paper-quiz/outcome", json={"question_id": first["question_id"], "outcome": "maybe"}).status_code in (409, 422)


def test_matching_ignores_case_spacing_and_a_plural_s():
    assert paper_quiz.matches("  Large Language  Models ", "large language model") and paper_quiz.matches("Self-attention", "self attention")
    assert not paper_quiz.matches("", "x") and not paper_quiz.matches(None, "x") and not paper_quiz.matches("zebra", "softmax")


def test_sentences_that_make_poor_questions_are_not_used():
    base = {"passage_id": "p-1", "page_number": 1, "section": "1 Introduction"}
    good = "The router sends every token to two experts whose outputs are combined using softmax weights."
    assert paper_quiz._cloze({**base, "sentence": good, "matched_term": "softmax"})[1] == "softmax"
    for sentence, term in [("Figure 2: The softmax output of the router for one example token in the network.", "softmax"), ("The softmax is short.", "softmax"),
                           ("The mod- els are fine-tuned and then the softmax is applied to the router scores here.", "softmax"), (good, "attention")]:
        assert paper_quiz._cloze({**base, "sentence": sentence, "matched_term": term}) is None, sentence
