"""Tutor retrieval: aliases and acronyms name concepts, sentence-level search finds evidence for questions that name none, and every passage stays a verifiable quotation."""
import json
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.session_routes import pipeline
from backend.main import app
from backend.models import DetectedConcept, Paragraph
from backend.platform import platform
from backend.session import session_manager
from backend.session.context_retriever import ContextRetriever
from backend.tutor import grounding
from backend.tutor.tutor_provider import TutorProvider

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)

QUESTIONS = {
    "dpo": ["What is DPO?", "How does DPO avoid fitting a reward model?", "What is the KL constraint?", "why is dpo more stable than actor critic", "What is PPO and how is it used as a baseline?",
            "What does beta control?", "How is the win rate computed?", "What is the Bradley-Terry model?", "explain RLHF", "What datasets were used for the experiments?"],
    "mixtral": ["What is MoE?", "How does the router choose experts?", "What is SMoE?", "How many parameters does Mixtral use per token?", "What does the gating network do?",
                "How was the instruct model trained?", "What are the multilingual results?", "explain SFT", "What is the context length?", "How does routing behave across domains?"],
    "chain-of-thought": ["What is chain of thought prompting?", "What is CoT?", "Which reasoning tasks were evaluated?", "How does it help arithmetic reasoning?", "What is the GSM8K benchmark?",
                         "Does it work for commonsense questions?", "Why does it only help large models?", "What is the ablation study?", "How were the exemplars written?", "What is symbolic reasoning?"],
}


@pytest.fixture(scope="module")
def papers(tmp_path_factory):
    out = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PREREQAI_SESSION_DIR", str(tmp_path_factory.mktemp("sessions")))
        for pid in QUESTIONS:
            out[pid] = session_manager.get(platform.analyze(f"backend/prereqai_eval/benchmark/pdfs/{pid}.pdf")["session_id"]).paper
        session_manager.sessions.clear()
    return out


def evidence_for(paper, question):
    return grounding.select_evidence(paper, ContextRetriever().retrieve(paper, question).concepts, question)


@pytest.mark.parametrize("pid", sorted(QUESTIONS))
def test_at_least_eight_of_ten_representative_questions_retrieve_verifiable_evidence(papers, pid):
    paper, pages, got = papers[pid], None, 0
    pages = {p.page_number: p.text for p in paper.pages}
    for question in QUESTIONS[pid]:
        evidence = evidence_for(paper, question)
        if evidence:
            got += 1
            assert all(p["sentence"] in pages[p["page_number"]] and p["section"] for p in evidence)  # exact quotations of the page they cite
            assert len({p["passage_id"] for p in evidence}) == len(evidence) <= grounding.MAX_EVIDENCE
    assert got >= 8, f"{pid}: evidence for only {got} of 10 questions"


def test_aliases_and_acronyms_name_concepts(papers):
    names = lambda pid, q: ContextRetriever().retrieve(papers[pid], q).concepts
    assert "Direct Preference Optimization" in names("dpo", "What is DPO?") and "Direct Preference Optimization" in names("dpo", "tell me about direct preference optimization")
    assert "Mixture of Experts" in names("mixtral", "What is MoE?") and "Chain-of-Thought" in names("chain-of-thought", "What is chain of thought prompting?")
    assert names("dpo", "What is the weather today?") == []


def test_a_question_that_names_no_concept_is_answered_from_the_sentences_that_contain_its_words(papers):
    evidence = evidence_for(papers["dpo"], "What is the KL constraint?")
    assert evidence and "KL" in evidence[0]["sentence"]  # the acronym is the topic, even though it names no registry concept
    assert evidence_for(papers["dpo"], "What is the airspeed velocity of an unladen swallow?") == []  # nothing relevant: no evidence is invented


class Model(TutorProvider):
    name, model = "gemini", "fake"

    def __init__(self, make):
        self.make, self.prompts = make, []

    def generate(self, system_prompt, user_prompt):
        self.prompts.append(user_prompt)
        return json.dumps({"answer": "It is a method the paper describes.", "confidence": 0.6, **self.make(json.loads(user_prompt)["paper_excerpts"])})


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.setenv("PREREQAI_TUTOR_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    session_manager.sessions.clear()
    pipeline.tutor._providers.clear()
    yield platform.analyze("backend/prereqai_eval/benchmark/pdfs/dpo.pdf")["session_id"]
    pipeline.tutor._providers.clear()
    session_manager.sessions.clear()


def ask(session, monkeypatch, make, question):
    model = Model(make)
    pipeline.tutor._providers.clear()
    monkeypatch.setattr("backend.tutor.gemini_tutor_provider.GeminiTutorProvider", lambda *a, **k: model)
    return client.post(f"/api/session/{session}/question", json={"question": question}).json()["responses"][0], model


def cite(excerpts):
    return {"citations": [{"passage_id": excerpts[0]["passage_id"], "quote": excerpts[0]["text"][:60]}]}


@pytest.mark.parametrize("question", ["What is DPO?", "What is the KL constraint?"])
def test_a_model_answer_to_an_alias_or_unnamed_question_is_verified_against_the_retrieved_passages(session, monkeypatch, question):
    response, model = ask(session, monkeypatch, cite, question)
    assert model.prompts and response["grounding"] == "verified" and response["provider"].startswith("gemini")
    assert response["citations"][0]["sentence"] and response["citations"][0]["page_number"]


@pytest.mark.parametrize("make", [lambda ex: {"citations": [{"passage_id": "p-0000000000", "quote": "an invented quotation that is not there"}]},
                                  lambda ex: {"citations": [{"passage_id": ex[0]["passage_id"], "quote": "text the passage does not contain at all"}]}, lambda ex: {}])
def test_no_generated_answer_to_these_questions_bypasses_verification(session, monkeypatch, make):
    response, _ = ask(session, monkeypatch, make, "What is DPO?")
    assert response["grounding"] == "fallback" and response["provider"] == "built-in" and response["citations"] == [] and "(ungrounded)" in response["notes"][0]


def test_a_question_with_no_evidence_still_gets_the_extractive_or_built_in_answer(session, monkeypatch):
    response, model = ask(session, monkeypatch, lambda ex: pytest.fail("the model must not be called"), "What is the airspeed velocity of an unladen swallow?")
    assert model.prompts == [] and response["grounding"] == "fallback" and response["answer"]
