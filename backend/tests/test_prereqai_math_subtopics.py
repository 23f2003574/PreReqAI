"""Equation-driven mathematical subtopics: the DPO loss and the attention equation name the specific skills they need, each traceable to its equation, page and number."""
import pytest

from backend.models import Equation
from backend.parsing.math_subtopics import analyse, subtopics_of

pytestmark = pytest.mark.prereqai
DPO = "LDPO(πθ; πref) = −E(x,yw,yl)∼D [ log σ (β log πθ(yw|x) / πref(yw|x) − β log πθ(yl|x) / πref(yl|x))]"
ATTENTION = "Attention(Q, K, V) = softmax(QKT / √dk)V"
GRADIENT = "∇θ L(θ) = ∂L/∂θ"
PLAIN = "Our model has three layers and a learning rate of five."


def names(expression):
    return {topic for topic, *_ in subtopics_of(expression)}


def test_the_dpo_loss_needs_expectation_sampling_conditional_probability_logs_and_the_sigmoid():
    assert {"Expectation of a random variable", "Sampling from a distribution (x ~ D)", "Conditional probability", "Cross-entropy and log-likelihood", "Sigmoid and logistic functions",
            "Logarithms and exponentials"} <= names(DPO)


def test_the_attention_equation_needs_matrix_products_softmax_and_scaling():
    assert {"Matrix multiplication and transpose", "Softmax and normalised exponentials", "Vector norms and dot products"} <= names(ATTENTION)
    assert "Gradients and partial derivatives" in names(GRADIENT) and "Kullback-Leibler divergence" in names("DKL(p || q) = E[log p/q]") and names(PLAIN) == set()


def test_every_recommendation_traces_to_its_equations_ranked_by_how_many_need_it_with_a_study_link():
    equations = [Equation(1, ATTENTION, "3.2 Attention", 4, "1", ""), Equation(2, DPO, "4 DPO", 5, "7", ""), Equation(3, "Attention(Q, K, V) = softmax(QKT)V", "3.2 Attention", 4, "2", ""),
                 Equation(4, PLAIN, "1 Intro", 1, "", "")]
    ranked = analyse(equations)
    top = {t["subtopic"]: t for t in ranked}
    assert top["Softmax and normalised exponentials"]["equation_count"] == 2 and ranked[0]["equation_count"] == 2
    assert [q["tag"] for q in top["Softmax and normalised exponentials"]["equations"]] == ["1", "2"] and top["Conditional probability"]["equations"][0]["page_number"] == 5
    assert all(t["equations"] and all(q["matched"] and q["section"] for q in t["equations"]) for t in ranked)  # nothing is recommended without an equation
    assert all(4 not in [q["equation_id"] for q in t["equations"]] for t in ranked)
    assert top["Conditional probability"]["subject"] == "Probability" and top["Conditional probability"]["resource"]["url"].startswith("https://")
    assert [t["equation_count"] for t in ranked] == sorted((t["equation_count"] for t in ranked), reverse=True)


def test_without_equations_there_is_nothing_to_recommend_and_a_missing_resource_is_none():
    assert analyse([]) == []
    assert analyse([Equation(1, ATTENTION, "s", 1, "", "")], resource_for=lambda subject: None)[0]["resource"] is None
