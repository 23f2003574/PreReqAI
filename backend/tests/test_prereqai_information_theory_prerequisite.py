"""Diffusion papers get Information Theory (entropy, KL divergence) in the plan, ordered after Probability, with a resource,
a justification, a tutor definition and a tree entry; papers that do not need it are unaffected."""
import pymupdf
from starlette.testclient import TestClient

from backend.main import app


def _session(tmp_path, text, data=None):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), text, fontsize=10)
    doc.save(path)
    client = TestClient(app)
    with open(path, "rb") as handle:
        body = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data or {}).json()
    return client, body


DIFFUSION = "Abstract\nWe present a diffusion model trained with score matching and a reverse process.\n"


def test_diffusion_paper_plans_information_theory_after_probability(tmp_path):
    _, body = _session(tmp_path, DIFFUSION)
    report = body["report"]
    plan = [(step["concept"], step["estimated_hours"]) for step in report["learning_plan"]]
    assert plan == [("Probability", 10), ("Information Theory", 8), ("Calculus", 10), ("Neural Networks", 15)]
    resource = next(r for r in report["learning_resources"] if r["concept"] == "Information Theory")
    assert resource["url"] == "https://www.inference.org.uk/mackay/itila/"
    reason = next(j for j in report["prerequisite_justifications"] if j["concept"] == "Information Theory")
    assert "KL divergence" in reason["justification"]


def test_tutor_defines_it_and_known_skips_it(tmp_path):
    client, body = _session(tmp_path, DIFFUSION)
    answer = client.post(f"/api/session/{body['session_id']}/question", json={"question": "Why do I need information theory?"}).json()["responses"][0]["answer"]
    assert answer.startswith("Information Theory: The mathematics of information: entropy and KL divergence")
    assert "Why it is needed here: Diffusion training objectives" in answer
    _, known = _session(tmp_path, DIFFUSION, {"known": "information theory"})
    assert [s["concept"] for s in known["report"]["learning_plan"]] == ["Probability", "Calculus", "Neural Networks"]
    assert known["warnings"] == []


def test_papers_without_diffusion_concepts_do_not_get_it(tmp_path):
    _, body = _session(tmp_path, "Abstract\nWe study a transformer with attention and softmax.\n")
    assert "Information Theory" not in [step["concept"] for step in body["report"]["learning_plan"]]
