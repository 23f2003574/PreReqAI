"""Cited titles in the bibliography are not the paper's own content: they must not add concepts or study steps."""
import json

import pymupdf
import pytest

from backend.cli import main

BODY = "Abstract\nWe study a transformer with attention.\n\n1 Introduction\nAttention is useful.\n\n"
CITED = ("[1] Kipf. Graph convolutional networks.\n[2] Velickovic. Graph attention networks and message passing.\n"
         "[3] Sutton. Policy gradient methods. Q-learning.\n[4] Ho. Denoising diffusion probabilistic models.\n")


def _report(tmp_path, capsys, text):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), text, fontsize=10)
    doc.save(path)
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    return json.loads(capsys.readouterr().out)["report"]


@pytest.mark.parametrize("heading", ["References", "REFERENCES", "7 References", "Bibliography"])
def test_cited_titles_add_no_concepts_or_study_steps(tmp_path, capsys, heading):
    report = _report(tmp_path, capsys, BODY + f"{heading}\n" + CITED)
    assert report["concepts"] == ["Transformer", "Attention"]
    plan = [s["concept"] for s in report["learning_plan"]]
    assert "Graphs" not in plan and "Markov Decision Process" not in plan


def test_the_same_concept_in_the_body_is_still_detected_and_counted_only_there(tmp_path, capsys):
    text = BODY.replace("Attention is useful.", "Attention is useful, and so is a graph neural network.") + "References\n" + CITED
    report = _report(tmp_path, capsys, text)
    assert "Graph Neural Network" in report["concepts"]
    assert "Policy Gradient" not in report["concepts"] and "Graph Attention Network" not in report["concepts"]


def test_a_paper_without_a_references_section_is_unchanged(tmp_path, capsys):
    report = _report(tmp_path, capsys, BODY + "2 Method\nA policy gradient method.\n")
    assert "Policy Gradient" in report["concepts"]
