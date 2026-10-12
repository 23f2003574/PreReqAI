"""Policy-gradient, score-matching and diffusion-reverse papers rely on derivatives; the plan must include Calculus."""
import json

import pymupdf

from backend.cli import main


def _analyse(tmp_path, capsys, text, *extra):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), text, fontsize=10)
    doc.save(path)
    assert main(["prerequisites", "analyze", str(path), "--json", *extra]) == 0
    return json.loads(capsys.readouterr().out)["report"]


def test_policy_gradient_paper_plans_calculus_with_resource_and_justification(tmp_path, capsys):
    report = _analyse(tmp_path, capsys, "Abstract\nWe study a policy gradient method over a Markov decision process.\n")
    plan = [s["concept"] for s in report["learning_plan"]]
    assert "Calculus" in plan
    assert "Calculus" in [r["concept"] for r in report["study_roadmap"]]
    just = {j["concept"]: j["justification"] for j in report["prerequisite_justifications"]}
    assert "derivative" in just["Calculus"].lower()


def test_known_calculus_is_left_out_of_the_plan(tmp_path, capsys):
    report = _analyse(tmp_path, capsys, "Abstract\nScore matching trains a diffusion model.\n", "--known", "Calculus")
    assert "Calculus" not in [s["concept"] for s in report["learning_plan"]]
