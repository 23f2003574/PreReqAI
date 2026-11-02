"""'Quiz me on Softmax' returns that concept's practice questions with answers, through the CLI."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]


def _ask(question):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask",
                          "examples/prerequisites/sample-paper.pdf", question],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


def test_quiz_me_on_a_concept_returns_its_questions_and_answers():
    assert _ask("Quiz me on Softmax") == (
        "Softmax Q1 (Easy): Why does Softmax produce probabilities instead of raw scores? "
        "Answer: Because it normalizes values into a probability distribution.")


def test_quiz_with_no_concept_named_covers_the_paper_concepts_that_have_questions():
    answer = _ask("Quiz me")
    assert "Attention Q1" in answer and "Softmax Q1" in answer and "Transformer Q1" in answer


def test_quiz_on_a_concept_without_questions_says_so_and_a_normal_question_is_unchanged():
    assert _ask("Quiz me on Recurrent Neural Network") == "There are no practice questions yet for Recurrent Neural Network."
    assert _ask("What is softmax?").startswith("Softmax: ")


def test_a_topic_scopes_the_quiz_over_http_and_the_cli_alike():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    with open(ROOT / "examples/prerequisites/sample-paper.pdf", "rb") as pdf:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", pdf, "application/pdf")}).json()["session_id"]

    def http(topic):
        return client.post(f"/api/session/{sid}/question", json={"question": "Quiz me", "topic": topic}).json()["responses"][0]["answer"]

    def cli(topic):
        run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", "examples/prerequisites/sample-paper.pdf",
                              "Quiz me", "--topic", topic], cwd=ROOT, capture_output=True, text=True, timeout=120)
        return run.stdout.splitlines()[0]

    assert http("Softmax") == cli("Softmax") == _ask("Quiz me on Softmax")
    assert http("Attention").startswith("Attention Q1") and "Softmax" not in http("Attention")
    assert http("Recurrent Neural Network") == cli("Recurrent Neural Network") == "There are no practice questions yet for Recurrent Neural Network."


def _quiz_in_process(question, concepts):
    from backend.models import DetectedConcept
    from backend.tutor.rule_based_tutor import RuleBasedTutor

    class Paper:
        pass

    paper, session = Paper(), Paper()
    paper.concepts = [DetectedConcept(name=name, domain="x", occurrences=1) for name in concepts]
    session.active_concept = None
    return RuleBasedTutor._quiz_answer(paper, session, question)


def test_quiz_covers_overfitting_and_the_other_core_concepts_that_used_to_have_no_questions():
    for name in ("Backpropagation", "Cross-Entropy Loss", "Overfitting", "Reinforcement Learning", "Diffusion Model", "Variational Autoencoder"):
        answer = _quiz_in_process(f"Quiz me on {name}", [])
        assert answer.startswith(f"{name} Q1 (") and "no practice questions" not in answer
    assert "Overfitting Q2 (Medium)" in _quiz_in_process("Quiz me", ["Overfitting"])


def test_quiz_on_a_concept_that_still_has_no_questions_says_so():
    assert _quiz_in_process("Quiz me on Q-Learning", []) == "There are no practice questions yet for Q-Learning."


def test_quiz_covers_gradient_descent_adam_and_dropout():
    answer = _quiz_in_process("Quiz me on Gradient Descent", [])
    assert answer.startswith("Gradient Descent Q1 (Easy)") and "Gradient Descent Q2 (Medium)" in answer
    for name in ("Adam Optimizer", "Dropout"):
        assert _quiz_in_process(f"Quiz me on {name}", []).startswith(f"{name} Q1 (")


@pytest.mark.parametrize("prerequisite", ["Calculus", "Linear Algebra", "Probability"])
def test_quiz_on_a_prerequisite_without_questions_says_so_instead_of_quizzing_other_concepts(prerequisite):
    answer = _ask(f"Quiz me on {prerequisite}")
    assert answer == f"There are no practice questions yet for {prerequisite}."


def test_quiz_naming_a_prerequisite_and_a_concept_with_questions_still_quizzes_the_concept():
    answer = _ask("Quiz me on Calculus and Softmax")
    assert answer.startswith("Softmax Q1") and "Attention Q1" not in answer
