"""A model-written tutor answer is shown as verified only when its citations match the stored evidence; everything else falls back to the built-in tutor."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.api.session_routes import pipeline
from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor import grounding
from backend.tutor.tutor_provider import ProviderError, TutorProvider

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)


class Model(TutorProvider):
    """A fake model: `make(excerpts)` builds its reply from the evidence it was shown, so each test decides what the model claims."""
    name, model = "gemini", "fake"

    def __init__(self, make):
        self.make, self.prompts = make, []

    def generate(self, system_prompt, user_prompt):
        self.prompts.append(user_prompt)
        reply = self.make(json.loads(user_prompt)["paper_excerpts"])
        return reply if isinstance(reply, str) else json.dumps({"answer": "Attention weighs the tokens.", "confidence": 0.7, **reply})


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    session_manager.sessions.clear()
    pipeline.tutor._providers.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    pipeline.tutor._providers.clear()
    session_manager.sessions.clear()


def ask(sid, monkeypatch, make, question="What is attention?"):
    model = Model(make)
    pipeline.tutor._providers.clear()
    monkeypatch.setenv("PREREQAI_TUTOR_PROVIDER", "gemini")
    monkeypatch.setattr("backend.tutor.gemini_tutor_provider.GeminiTutorProvider", lambda *a, **k: model)
    body = client.post(f"/api/session/{sid}/question", json={"question": question}).json()
    return body["responses"][0], body, model


def cite(excerpt, quote=None, **extra):
    return {"passage_id": excerpt["passage_id"], "quote": quote or excerpt["text"][:60], **extra}


def test_valid_citations_are_verified_and_returned_from_the_stored_passage(sid, monkeypatch):
    response, body, model = ask(sid, monkeypatch, lambda ex: {"citations": [cite(ex[0])]})
    assert response["provider"].startswith("gemini") and response["grounding"] == "verified" and response["notes"] == []
    [citation] = response["citations"]
    assert citation["sentence"] and citation["quote"] in " ".join(citation["sentence"].split()) and citation["section"] and citation["page_number"] == 1
    assert json.loads(model.prompts[0])["paper_excerpts"][0]["text"] == citation["sentence"]  # the evidence the model saw is the stored sentence


@pytest.mark.parametrize("make,why", [
    (lambda ex: {"citations": [{"passage_id": "p-0000000000", "quote": "attention weighs every token"}]}, "was not supplied"),
    (lambda ex: {"citations": [cite(ex[0], quote="attention secretly runs on quantum hardware")]}, "is not in that passage"),
    (lambda ex: {"citations": [cite(ex[0], quote=ex[0]["text"][:30].replace("e", "a"))]}, "is not in that passage"),  # an altered quotation
    (lambda ex: {"citations": [cite(ex[0], quote="short")]}, "is not in that passage"),
    (lambda ex: {"citations": []}, "cites no passage"),
    (lambda ex: {}, "cites no passage"),
    (lambda ex: {"citations": "p-1"}, "cites no passage"),
    (lambda ex: {"answer": "Attention improved accuracy by 42.7% in the paper.", "citations": [cite(ex[0])]}, "no cited passage supports"),
])
def test_invalid_generated_answers_never_reach_the_learner_as_verified(sid, monkeypatch, make, why):
    response, body, _ = ask(sid, monkeypatch, make)
    assert response["provider"] == "built-in" and response["grounding"] == "fallback" and response["citations"] == []
    assert "(ungrounded)" in response["notes"][0] and why in response["notes"][0] and "quotes the paper itself" in response["notes"][1]
    assert "Attention weighs the tokens" not in response["answer"] and "42.7" not in response["answer"] and response["answer"]  # the built-in answer is shown and usable
    assert response["notes"][0] in body["warnings"]


def test_a_number_from_the_cited_passage_or_the_question_is_allowed(sid, monkeypatch):
    def make(ex):
        digits = "".join(ch for ch in ex[0]["text"] if ch.isdigit())
        number = next((t for t in ex[0]["text"].replace(",", " ").split() if t.isdigit()), None)
        return {"answer": f"The passage mentions {number}." if number else "Attention weighs 3 things.", "citations": [cite(ex[0])]} if number else {"answer": "You asked about 7 things.", "citations": [cite(ex[0])]}

    response, *_ = ask(sid, monkeypatch, make, question="What is attention? I have 7 days.")
    assert response["grounding"] == "verified"


def test_no_evidence_means_the_model_is_not_asked_and_the_built_in_tutor_answers(sid, monkeypatch):
    response, body, model = ask(sid, monkeypatch, lambda ex: pytest.fail("the model must not be called"), question="What is the airspeed of a swallow?")
    assert model.prompts == [] and response["provider"] == "built-in" and response["grounding"] == "fallback"
    assert "(no_evidence)" in response["notes"][0] and response["answer"]


def test_a_provider_failure_still_falls_back_and_is_marked(sid, monkeypatch):
    def broken(excerpts):
        raise ProviderError("timeout", "Gemini did not answer in time.")

    response, *_ = ask(sid, monkeypatch, broken)
    assert response["provider"] == "built-in" and response["grounding"] == "fallback" and "(timeout)" in response["notes"][0]


def test_the_checks_are_deterministic_and_use_no_model():
    evidence = [{"passage_id": "p-1", "sentence": "We use attention and\nsoftmax instead of recurrence.", "page_number": 2, "section": "Method"}]
    raw = json.dumps({"citations": [{"passage_id": "p-1", "quote": "attention and softmax  instead"}]})
    first = grounding.verify(raw, "It replaces recurrence.", evidence)
    assert first == grounding.verify(raw, "It replaces recurrence.", evidence) and first[0]["page_number"] == 2 and first[0]["quote"] == "attention and softmax instead"
    with pytest.raises(ProviderError):
        grounding.verify(raw.replace("attention", "Attention"), "x", evidence)  # case is part of the quotation
    with pytest.raises(ProviderError, match="could not be checked"):
        grounding.verify("not json", "x", evidence)
