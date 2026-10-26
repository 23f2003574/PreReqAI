"""The study plan must be self-contained: every prerequisite the prerequisite tree shows is planned or already satisfied."""
import pymupdf
import pytest

from backend.platform import platform

PAPERS = {
    "transformer": "We study the Transformer with self-attention, multi-head attention and layer normalization.",
    "rl": "A Markov decision process with the Bellman equation, Q-learning, policy gradient and an actor-critic.",
    "graph": "A graph neural network with message passing, node embedding, a graph attention network and a GCN.",
    "diffusion": "A diffusion model with a forward process, a reverse process, a noise schedule, score matching and a U-Net.",
    "vision": "A convolutional neural network with batch normalization, dropout, backpropagation and gradient descent.",
}


def _tree_names(nodes):
    for node in nodes:
        yield node
        yield from _tree_names(node["prerequisites"])


@pytest.mark.parametrize("name", sorted(PAPERS))
def test_every_prerequisite_in_the_tree_is_planned_or_satisfied(name, tmp_path):
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), PAPERS[name], fontsize=6)
    path = tmp_path / f"{name}.pdf"
    document.save(str(path))

    report = platform.analyze(str(path))["report"]
    planned = {step["concept"] for step in report["learning_plan"]}
    detected = set(report["concepts"])
    assert detected, "the generated paper should have been recognised"

    for node in _tree_names(report["prerequisite_tree"]):
        # a paper concept is covered by the paper; anything else must be in the plan (or marked satisfied)
        assert node["concept"] in detected or node["concept"] in planned or node["satisfied"], \
            f"{node['concept']} is in the prerequisite tree of the {name} paper but not in its study plan"
    assert planned == {p["concept"] for p in report["prerequisites"] if p["concept"] not in detected}
    assert {j["concept"] for j in report["prerequisite_justifications"]} == planned | {
        p["concept"] for p in report["prerequisites"] if p["concept"] in detected}
