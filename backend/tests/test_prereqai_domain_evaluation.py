"""Evaluation of the analysis on one representative paper per focus area (RL, graph ML, diffusion, the bundled
transformer sample): the expected concepts and prerequisite plan, plus the invariants every report must satisfy,
so a regression in any stage shows up as a wrong plan or an inconsistent report."""
import json

import pymupdf
import pytest

from backend.cli import main

PAPERS = {
    "rl": ("Policy Optimization with Value Baselines",
           "We train a policy gradient agent with a value function in a Markov decision process, using reinforcement "
           "learning with a reward signal. Policy gradient variance is reduced by a baseline. "
           "The Markov decision process has states and actions.",
           {"Markov Decision Process", "Policy Gradient", "Value Function"}, ["Probability", "Calculus"], 20),
    "graph": ("Message Passing on Graphs",
              "A graph neural network aggregates messages over a graph. The graph convolutional network uses a graph "
              "Laplacian and spectral convolution. Graph neural network layers are stacked.",
              {"Graph Neural Network", "Message Passing", "Graph Convolution"}, ["Linear Algebra", "Graphs", "Neural Networks"], 35),
    "diffusion": ("Denoising Diffusion",
                  "We train a diffusion model with score matching, a noise schedule and a U-Net over the forward process.",
                  {"Diffusion Model", "Score Matching"}, ["Probability", "Information Theory", "Calculus", "Neural Networks"], 43),
}


def _analyze(path, capsys):
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    return json.loads(capsys.readouterr().out)["report"]


def _paper(tmp_path, title, body):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(60, 60, 540, 780), f"{title}\n\n1 Introduction\n{body}\n\nReferences\n[1] A. Paper. 2020.\n", fontsize=10)
    doc.save(path)
    return path


def _assert_report_is_consistent(report):
    plan = [step["concept"] for step in report["learning_plan"]]
    assert [step["step"] for step in report["learning_plan"]] == list(range(1, len(plan) + 1))
    assert report["study_time"]["total_hours"] == sum(step["estimated_hours"] for step in report["learning_plan"])
    assert [step["concept"] for step in report["study_roadmap"]] == plan
    assert [item["concept"] for item in report["study_progress"]] == plan
    assert report["readiness"]["total_concepts"] == len(plan) and report["readiness"]["completed_concepts"] == 0
    assert set(plan) <= {item["concept"] for item in report["prerequisite_justifications"]}  # every planned concept says why

    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node["prerequisites"])

    unsatisfied = {node["concept"] for node in walk(report["prerequisite_tree"]) if not node["satisfied"] and not node["prerequisites"]}
    assert unsatisfied <= set(plan)  # a leaf the learner must still learn is always in the study plan


@pytest.mark.parametrize("name", sorted(PAPERS))
def test_each_focus_area_gets_its_expected_concepts_and_plan(name, tmp_path, capsys):
    title, body, concepts, plan, hours = PAPERS[name]
    report = _analyze(_paper(tmp_path, title, body), capsys)
    assert {c["name"] if isinstance(c, dict) else c for c in report["concepts"]} >= concepts
    assert [step["concept"] for step in report["learning_plan"]] == plan
    if hours is not None:
        assert report["study_time"]["total_hours"] == hours
    _assert_report_is_consistent(report)


def test_the_bundled_sample_paper_report_is_consistent(capsys):
    _assert_report_is_consistent(_analyze("examples/prerequisites/sample-paper.pdf", capsys))
