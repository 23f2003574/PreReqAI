"""Paper comprehension beyond term recall: true/false claims, equation-to-subject questions and method-step ordering, each traceable to a verbatim quotation, plus alias-aware answer matching."""
from types import SimpleNamespace

import pytest

from backend.models import Equation, Paragraph
from backend.tutor import paper_quiz

pytestmark = pytest.mark.prereqai
S1 = "The Transformer computes softmax attention over every token of the input sequence in parallel."
S2 = "Each layer then applies a position-wise feed forward network to the attended representation."
S3 = "Finally the layer output is added to its input and normalised before the next layer begins."
METHOD = f"{S1} {S2} {S3}"
CLAIM_PAGE = "Gradient descent updates the parameters of the network after every batch of training examples seen."


def session():
    passages = [{"passage_id": "p-1", "sentence": CLAIM_PAGE, "matched_term": "Gradient descent", "page_number": 1, "section": "1 Introduction"},
                {"passage_id": "p-2", "sentence": S1, "matched_term": "softmax", "page_number": 2, "section": "3 Method"}]
    report = {"concept_evidence": [{"concept": "Gradient Descent", "passages": [passages[0]]}, {"concept": "Softmax", "passages": [passages[1]]}]}
    paper = SimpleNamespace(pages=[SimpleNamespace(page_number=1, text=CLAIM_PAGE), SimpleNamespace(page_number=2, text=METHOD.replace(". ", ".\n"))],
                            equations=[Equation(1, "Attention(Q, K, V) = softmax(QKT / √dk)V", "3 Method", 2, "1", ""), Equation(2, "L = −E(x,y)∼D [ log σ (r(x,y)) ]", "4 Loss", 3, "2", "")],
                            paragraphs=[Paragraph(7, "3 Method", METHOD, 2), Paragraph(8, "1 Introduction", METHOD, 1)])
    return SimpleNamespace(report=report, paper=paper, quiz_pending={}, quiz_attempts=[])


def test_three_kinds_of_question_are_built_each_with_a_verbatim_quotation_page_and_section():
    questions = paper_quiz.build_comprehension(session())
    kinds = [q["kind"] for q in questions]
    assert {"claim", "equation", "order"} <= set(kinds) and all(q["question_id"].split("~")[0] in ("claim", "equation", "order") and q["question_id"].endswith(":1") for q in questions)
    pages = {1: CLAIM_PAGE, 2: " ".join(METHOD.split())}
    for q in questions:
        assert q["quotation"] and q["page_number"] and q["section"]
        if q["kind"] in ("claim", "order"):
            assert " ".join(q["quotation"].split()) in pages[q["page_number"]], q  # an exact quotation of the page it cites
    assert len({q["question_id"] for q in questions}) == len(questions)


def test_a_claim_is_true_as_written_or_false_with_its_term_swapped_and_the_answer_is_never_in_the_prompt():
    session_ = session()
    claims = [q for q in paper_quiz.build_comprehension(session_) if q["kind"] == "claim"]
    assert claims[0]["answer"] == "true" and CLAIM_PAGE in claims[0]["prompt"]
    false = next(q for q in claims if q["answer"] == "false")
    assert false["quotation"] == S1 and "Gradient Descent" in false["prompt"] and "softmax" not in false["prompt"].lower()  # the original sentence is the quotation; the prompt is the altered one
    assert paper_quiz.check(claims[0], "True") and paper_quiz.check(claims[0], "t") and not paper_quiz.check(claims[0], "false")
    assert paper_quiz.check(false, "no") and not paper_quiz.check(false, "") and not paper_quiz.check(false, "maybe")


def test_equation_questions_ask_for_the_subject_from_four_options_and_ordering_questions_are_shuffled_but_checkable():
    questions = paper_quiz.build_comprehension(session())
    equation = next(q for q in questions if q["kind"] == "equation")
    assert equation["answer"] in paper_quiz.MATH_SUBJECTS and equation["prompt"].count(",") >= 3 and "page" in equation["prompt"] and paper_quiz.check(equation, equation["answer"].upper())
    assert not paper_quiz.check(equation, "Graphs")
    order = next(q for q in questions if q["kind"] == "order")
    assert order["answer"] != "A B C" and all(x in order["prompt"] for x in (S1, S2, S3)) and order["quotation"] == f"{S1} {S2} {S3}"
    assert paper_quiz.check(order, order["answer"]) and paper_quiz.check(order, order["answer"].replace(" ", ", ")) and not paper_quiz.check(order, "A B C")

def test_find_serves_every_kind_by_id_and_public_questions_hide_the_answer():
    s = session()
    for q in paper_quiz.build_comprehension(s):
        number, found = paper_quiz.find(s, q["question_id"])
        assert found["question_id"] == q["question_id"] and number
        shown = paper_quiz.public(q, 1, 3)
        assert "answer" not in shown and "quotation" not in shown and shown["kind"] == q["kind"]


@pytest.mark.parametrize("typed, answer, aliases, expected", [("bias", "bia", (), False), ("bia", "bias", (), False), ("models", "model", (), True), ("Model", "models", (), True),
                                                              ("self attention", "Self-Attention", (), True), ("SGD", "stochastic gradient descent", ("SGD",), True), ("", "x", (), False),
                                                              ("loss", "los", (), False), ("class", "classes", (), True)])
def test_matching_is_alias_aware_and_a_plural_never_makes_two_different_words_equal(typed, answer, aliases, expected):
    assert paper_quiz.matches(typed, answer, aliases) is expected


def test_a_paper_without_equations_or_method_sections_just_has_fewer_kinds():
    s = session()
    s.paper.equations, s.paper.paragraphs = [], []
    assert {q["kind"] for q in paper_quiz.build_comprehension(s)} == {"claim"}
