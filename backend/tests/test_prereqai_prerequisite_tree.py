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


def _linear_algebra(report):
    return _find(_find(_find(report["prerequisite_tree"], "Transformer")["prerequisites"], "Attention")["prerequisites"], "Linear Algebra")


def test_marking_a_concept_studied_updates_the_tree_of_the_session_and_undo_reverts_it():
    from backend.session import session_manager

    sid = platform.analyze(SAMPLE)["session_id"]
    assert _linear_algebra(session_manager.get(sid).report)["studied"] is False
    platform.mark_concept_studied(sid, "Linear Algebra")
    assert _linear_algebra(session_manager.get(sid).report)["studied"] is True
    platform.unmark_concept_studied(sid, "Linear Algebra")
    assert _linear_algebra(session_manager.get(sid).report)["studied"] is False


def test_studied_at_analysis_time_shows_in_the_tree():
    report = platform.analyze(SAMPLE, studied=["Linear Algebra"])["report"]
    assert _linear_algebra(report)["studied"] is True


def test_the_session_endpoint_returns_the_tree_and_it_follows_study_progress():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    sid = platform.analyze(SAMPLE)["session_id"]
    studied = lambda: _linear_algebra({"prerequisite_tree": client.get(f"/api/session/{sid}").json()["prerequisite_tree"]})["studied"]

    assert studied() is False
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Linear Algebra"})
    assert studied() is True
