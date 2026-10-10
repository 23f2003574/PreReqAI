import json

import pymupdf

from backend.cli import main


def test_a_diffusion_paper_gets_prerequisites_and_a_study_plan(tmp_path, capsys):
    path = tmp_path / "ddpm.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(
        pymupdf.Rect(50, 50, 550, 780),
        "Diffusion Models\nWe train a diffusion model with score matching, a noise schedule and a U-Net "
        "over the forward process.", fontsize=11)
    doc.save(path)

    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]

    concepts = {c["name"] if isinstance(c, dict) else c for c in report["concepts"]}
    assert {"Diffusion Model", "Score Matching"} <= concepts
    assert {"Probability", "Neural Networks"} <= {p["concept"] for p in report["prerequisites"]}
    assert {"Probability", "Neural Networks"} <= {s["concept"] for s in report["learning_plan"]}
    assert report["study_time"]["total_hours"] > 0
