"""'Which prerequisites does Softmax need?' lists what that concept builds on, not only its definition."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ask(question, *flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask",
                          "examples/prerequisites/sample-paper.pdf", question, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


def test_a_concept_question_lists_its_prerequisites():
    assert _ask("Which prerequisites does Softmax need?") == "Softmax builds on Probability."


def test_studied_prerequisites_are_marked():
    assert _ask("What are the prerequisites of Backpropagation?", "--studied", "Calculus") == \
        "Backpropagation builds on Calculus (studied), Neural Networks."


def test_a_why_question_still_gets_the_definition():
    assert _ask("What is softmax?").startswith("Softmax: ")


def test_progress_question_reports_studied_count_and_names():
    assert _ask("How much have I completed?", "--studied", "Probability,Calculus") == \
        "You have studied 2 of 4 planned prerequisites (50%). Studied: Probability, Calculus."
    assert _ask("What is my progress?") == "You have studied 0 of 4 planned prerequisites (0%)."


def test_concepts_question_lists_detected_concepts_most_mentioned_first():
    assert _ask("Which concepts does this paper cover?") == (
        "The paper discusses these concepts, most mentioned first: Attention (4x), Softmax (3x), "
        "Gradient Descent (2x), Transformer (1x), Backpropagation (1x).")


def test_a_prerequisite_that_is_only_a_registry_concept_still_gets_its_definition(tmp_path):
    import pymupdf

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "We use a graph attention network over node features.", fontsize=10)
    path = tmp_path / "gat.pdf"
    document.save(str(path))
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", str(path), "Why do I need attention?"],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    assert run.stdout.startswith("Attention: A mechanism that allows a model to focus on the most relevant parts of an input sequence. Why it is needed here:")


def _equation_paper(count):
    from types import SimpleNamespace

    return SimpleNamespace(equations=[SimpleNamespace(equation_id=i, expression=f"y_{i} =\n softmax(x)", section="Method") for i in range(1, count + 1)])


def test_equation_question_lists_extracted_equations():
    from backend.tutor.rule_based_tutor import RuleBasedTutor

    answer = RuleBasedTutor._study_plan_answer(_equation_paper(7), "Which equations are in the paper?")
    assert answer == ("The paper has 7 extracted equations: (1) y_1 = softmax(x) [Method]; (2) y_2 = softmax(x) [Method]; "
                      "(3) y_3 = softmax(x) [Method]; (4) y_4 = softmax(x) [Method]; (5) y_5 = softmax(x) [Method] and 2 more.")
    assert RuleBasedTutor._study_plan_answer(_equation_paper(1), "show me the formula").startswith("The paper has 1 extracted equation: (1)")
    assert RuleBasedTutor._study_plan_answer(_equation_paper(0), "What equations does it use?") == "No equations were extracted from this paper."


def test_equation_question_through_the_cli_on_a_paper_without_equations():
    assert _ask("Which equations are in the paper?") == "No equations were extracted from this paper."
