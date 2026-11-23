"""Mathematical extraction and subtopic rules on equations extracted from the real PDFs (AI-annotated, provisional, unreviewed fixture), and the filter for non-equations the text layer reports."""
import pytest

from backend.parsing import equation_extractor, math_subtopics
from backend.prereqai_eval import gate, math_eval, retrieval_real
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai


@pytest.fixture(scope="module")
def papers():
    ids = {item["paper"] for item in math_eval.load_real()["items"]}
    return {pid: session_manager.get(platform.analyze(path)["session_id"]).paper for pid, path in retrieval_real.pdf_paths(ids).items()}


@pytest.mark.parametrize("text", ["N=16", "N = 1", "DPO (temp = 1.0)", "Mean (alpha = 0.05)", "ref_yw_logps, ref_yl_logps = ref_logps[yw_idxs], ref_logps[yl_idxs]", "losses = -F.logsigmoid(beta * (pi_logratios - ref_logratios))",
                                  "n + 1): j = min(i, r); while j > 0: C[j] += C[j - 1]; j -= 1; return C[r]"])
def test_labels_legends_and_code_are_not_equations(text):
    assert equation_extractor.looks_like_non_equation(text)


@pytest.mark.parametrize("text", ["LDPO(πθ; πref) = −E(x,yw,yl)∼D [ log σ ( β log πθ(yw | x) πref(yw | x) −β log πθ(yl | x) πref(yl | x) )]", "G(x) := Softmax(TopK(x · Wg))", "r(x, y) = β log", "x = 2y + 1", "p(y|x) = 0.5"])
def test_real_equations_are_kept(text):
    assert not equation_extractor.looks_like_non_equation(text)


@pytest.mark.parametrize("expression,topic", [
    ("p∗(y1 ≻y2 | x) = exp (r∗(x, y1)) + exp (r∗(x, y2)). exp (r∗(x, y1))", "Conditional probability"),
    ("p∗(τ|y1, . . . , yK, x) = k=1 Y K PK j=k exp(r∗(x, yτ(j))) exp(r∗(x, yτ(k)))", "Softmax and normalised exponentials"),
    ("Z(x) = P y πref(y | x) exp ( 1 β r(x, y) )", "Summation and product notation"),
    ("y = n−1 X i=0 Softmax(Top2(x · Wg))i · SwiGLUi(x)", "Matrix multiplication and transpose"),
    ("min π Ex∼D [ Ey∼π(y|x) [ log π(y|x) π∗(y|x) ] ]", "Optimisation objectives (argmin and argmax)"),
    ("p∗ = 1 + exp ( β log π∗(y2|x) πref(y2|x) )", "Sigmoid and logistic functions"),
    ("r′(x, y) = β log πr(y|x) πref(y|x)", "Logarithms and exponentials"),
    ("LDPO(πθ, πref) = −Eτ,y1,...,yK,x∼D", "Expectation of a random variable")])
def test_each_rule_extension_finds_what_the_text_layer_leaves(expression, topic):
    assert topic in {name for name, _, _, _ in math_subtopics.subtopics_of(expression)}


@pytest.mark.parametrize("expression,topic", [
    ("r(x, y) = rϕ(x, y) −β(log πθ(y | x) -log πref(y | x))", "Cross-entropy and log-likelihood"),  # a difference of logs is a log-ratio, not a negative log-likelihood
    ("N = 16 and the log of the loss", "Logarithms and exponentials"),
    ("a + b P c", "Summation and product notation"),
    ("Each token is chosen ~ at random", "Expectation of a random variable")])
def test_the_extensions_do_not_overreach(expression, topic):
    assert topic not in {name for name, _, _, _ in math_subtopics.subtopics_of(expression)}


def test_the_fixture_is_labelled_provisional_and_internally_consistent():
    data = math_eval.load_real()
    assert data["status"] == "ai_annotated_provisional_unreviewed" and "NOT reviewed by a human" in data["provenance"]
    names = {rule[0] for rule in math_subtopics.RULES}
    ids = [item["id"] for item in data["items"]]
    assert len(ids) == len(set(ids)) and all(set(item["expected"]) <= names for item in data["items"]) and all(not item["expected"] for item in data["items"] if not item["is_equation"])


def test_real_extraction_and_rules_meet_the_measured_floors(papers):
    report = math_eval.evaluate_real(papers)
    assert report["annotated_equations"] >= 40 and not report["unannotated"]  # the extraction did not change under the annotations
    assert report["extraction_precision"] >= 0.95 and report["extraction_recall"] >= 0.93 and report["precision"] >= 0.95 and report["recall"] >= 0.95  # baseline before the fixes: 0.754 / 0.956 / 0.978 / 0.740
    assert set(report["per_subtopic"]) >= {"Softmax and normalised exponentials", "Summation and product notation", "Conditional probability"}
    assert report["false_negatives"] == ["dpo-14: Kullback-Leibler divergence", "dpo-20: Cross-entropy and log-likelihood"]  # the remaining known misses, named


def test_a_degraded_rule_set_and_a_lost_filter_fail_the_real_checks(papers):
    nothing = math_eval.evaluate_real(papers, subtopics_of=lambda text: [])
    assert nothing["recall"] == 0.0
    checks = []
    gate.real_math_checks(checks, gate.load_thresholds()["math_real"], papers)
    assert checks and all(c["passed"] for c in checks) and {c["metric"] for c in checks} == {"precision", "recall", "extraction_precision", "extraction_recall", "annotated_equations"}
    floors = {"recall": 0.95}
    bad = []
    gate.real_math_checks(bad, floors, {pid: papers[pid] for pid in ("dpo",)})
    assert all(c["passed"] for c in bad)
    from unittest.mock import patch
    with patch.object(math_eval, "evaluate_real", return_value={**math_eval.evaluate_real(papers), "recall": 0.5, "papers": [], "annotated_equations": 45, "false_extractions": [], "unannotated": []}):
        failing = []
        gate.real_math_checks(failing, {"recall": 0.95}, papers)
    assert [c["passed"] for c in failing] == [False]
