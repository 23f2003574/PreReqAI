"""The report carries a prerequisite tree: each paper concept expanded into the chain of what it needs."""
from backend.platform import platform

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _find(nodes, name):
    return next(node for node in nodes if node["concept"] == name)


def test_tree_expands_prerequisites_of_prerequisites():
    tree = platform.analyze(SAMPLE)["report"]["prerequisite_tree"]
    transformer = _find(tree, "Transformer")
    attention = _find(transformer["prerequisites"], "Attention")
    assert [n["concept"] for n in attention["prerequisites"]] == ["Linear Algebra", "Probability"]
    assert _find(tree, "Backpropagation")["prerequisites"]


def test_a_concept_without_prerequisites_has_no_tree():
    tree = platform.analyze(SAMPLE)["report"]["prerequisite_tree"]
    assert "Linear Algebra" not in {n["concept"] for n in tree}


def test_known_concept_is_marked_satisfied_everywhere_in_the_tree():
    plain = platform.analyze(SAMPLE)["report"]["prerequisite_tree"]
    known = platform.analyze(SAMPLE, known=["Calculus"])["report"]["prerequisite_tree"]
    calculus = lambda tree: _find(_find(tree, "Gradient Descent")["prerequisites"], "Calculus")["satisfied"]
    assert calculus(plain) is False and calculus(known) is True
