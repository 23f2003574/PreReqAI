"""`prerequisites ask` as the user runs it: analyse a PDF and answer a question in one command."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _ask(*args):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", *args],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    return run.returncode, run.stdout, run.stderr


def test_a_concept_question_prints_the_built_in_answer_and_discloses_the_missing_model():
    code, out, err = _ask(SAMPLE, "What is softmax?")
    assert code == 0 and err == ""
    assert "Softmax: A mathematical function" in out and "concepts: Softmax" in out
    assert "No tutoring model is configured" in out and "built-in definitions" in out


def test_json_output_carries_the_session_answers_and_warning():
    code, out, _ = _ask(SAMPLE, "Why do I need calculus?", "--json")
    body = json.loads(out)
    assert code == 0 and body["status"] == "success" and body["session_id"]
    assert "derivatives" in body["responses"][0]["answer"] and len(body["responses"]) == 1
    assert body["warnings"]


def test_an_unrelated_question_keeps_the_disclosed_placeholder():
    code, out, _ = _ask(SAMPLE, "hello")
    assert code == 0 and "tutoring model has not yet been configured" in out and "placeholder" in out


def test_a_blank_question_is_a_usage_error_and_a_missing_paper_fails_readably():
    code, out, err = _ask(SAMPLE, "   ")
    assert code == 2 and out == "" and "must not be empty" in err
    code, out, err = _ask("/no/such/paper.pdf", "What is softmax?")
    assert code == 1 and out == "" and "analysis failed" in err and "Traceback" not in err
