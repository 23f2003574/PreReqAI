"""Papers on training basics (SGD, backprop, CNNs, BatchNorm, dropout) are recognised and get a study plan."""
import json

import pymupdf

from backend.cli import main


def _report(tmp_path, capsys, text):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), text, fontsize=10)
    doc.save(path)
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    return json.loads(capsys.readouterr().out)["report"]


def test_a_cnn_training_paper_gets_concepts_and_a_plan_with_calculus(tmp_path, capsys):
    report = _report(tmp_path, capsys,
                     "Abstract\nWe train a CNN with SGD and backprop, using BatchNorm and dropout.\n")
    names = {c["name"] if isinstance(c, dict) else c for c in report["concepts"]}
    assert {"Gradient Descent", "Backpropagation", "Convolutional Neural Network",
            "Batch Normalization", "Dropout"} <= names
    plan = [s["concept"] for s in report["learning_plan"]]
    assert {"Calculus", "Linear Algebra", "Probability", "Neural Networks"} <= set(plan)
    assert [s["concept"] for s in report["study_roadmap"]] == plan


def test_backpropagation_depends_on_gradient_descent_in_the_concept_graph(tmp_path, capsys):
    report = _report(tmp_path, capsys, "Abstract\nBackpropagation updates weights by gradient descent.\n")
    explained = " ".join(json.dumps(report).split())
    assert "Backpropagation" in explained and "Gradient Descent" in explained
