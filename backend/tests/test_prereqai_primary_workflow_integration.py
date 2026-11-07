"""One generated academic PDF through the real CLI: section extraction, concept identification, prerequisite mapping and the
study plan must agree with each other, not just each be present."""
import json

import pymupdf

from backend.cli import main

TEXT = ("Policy Learning with Attention\n\nAbstract\nWe study a policy gradient agent.\n\n"
        "1 Introduction\nReinforcement learning needs a Markov decision process.\n\n"
        "2 Method\nThe transformer uses multi-head attention and softmax.\n\n3 Experiments\nWe evaluate on benchmarks.\n\n"
        "References\n[1] A. Author. Title. 2020.\n")


def test_pdf_to_study_plan_stages_agree_with_each_other(tmp_path, capsys):
    path = tmp_path / "paper.pdf"
    document = pymupdf.open()
    document.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), TEXT, fontsize=10)
    document.save(path)

    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "success" and result["warnings"] == []
    report = result["report"]

    # sections: front matter, the four headed sections and the references were split out of the one page
    assert report["paper"]["title"] == "Policy Learning with Attention"
    assert report["statistics"]["sections"] == 6 and report["statistics"]["references"] == 1

    # concepts: found in different sections of the paper
    concepts = set(report["concepts"])
    assert {"Policy Gradient", "Markov Decision Process", "Transformer", "Multi-Head Attention", "Softmax"} <= concepts

    # prerequisites: every reason names a concept the paper really discusses; the detected set drives the tree
    for item in report["prerequisites"]:
        assert any(name in item["reason"] for name in concepts), item
    assert set(report["learning_paths"]) == concepts

    # plan: exactly the prerequisites the paper does not cover, numbered from 1, whose hours add up to the study time
    missing = {m["concept"] for m in report["missing_prerequisites"] if not m["satisfied"]}
    plan = report["learning_plan"]
    assert {s["concept"] for s in plan} == missing and "Attention" not in missing  # Attention is covered within the paper
    assert [s["step"] for s in plan] == list(range(1, len(plan) + 1))
    assert sum(s["estimated_hours"] for s in plan) == report["study_time"]["total_hours"] > 0
    assert [p["concept"] for p in report["study_progress"]] == [s["concept"] for s in plan]
    assert report["readiness"]["total_concepts"] == len(plan) and not report["readiness"]["ready_to_read"]
