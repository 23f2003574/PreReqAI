"""--known / `known` must leave the paper's difficulty consistent with the personalised plan."""
import json

import pymupdf
from starlette.testclient import TestClient

from backend.cli import main
from backend.main import app

TEXT = "Abstract\nA transformer with a graph neural network, a policy gradient agent and a diffusion model.\n"


def _pdf(tmp_path):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), TEXT, fontsize=10)
    doc.save(path)
    return path


def _cli_report(path, capsys, *known):
    flags = [f for name in known for f in ("--known", name)]
    assert main(["prerequisites", "analyze", str(path), "--json", *flags]) == 0
    return json.loads(capsys.readouterr().out)["report"]


def _missing(report):
    return sum(1 for p in report["missing_prerequisites"] if not p["satisfied"])


def test_difficulty_counts_only_prerequisites_still_missing(tmp_path, capsys):
    path = _pdf(tmp_path)
    base = _cli_report(path, capsys)
    assert _missing(base) >= 3 and base["paper_difficulty"]["level"] != "Beginner"
    assert f"{_missing(base)} prerequisite concepts" in base["paper_difficulty"]["explanation"]

    plan = [s["concept"] for s in base["learning_plan"]]
    known = _cli_report(path, capsys, *plan[:-1])
    assert _missing(known) == 1
    assert known["paper_difficulty"]["level"] == "Beginner" and known["paper_difficulty"]["score"] < base["paper_difficulty"]["score"]
    assert known["paper_difficulty"]["explanation"].startswith("1 prerequisite concepts")


def test_difficulty_explanations_follow_the_remaining_gaps(tmp_path, capsys):
    path = _pdf(tmp_path)
    base = _cli_report(path, capsys)
    everything = _cli_report(path, capsys, *[s["concept"] for s in base["learning_plan"]])
    assert any(e["title"] == "Missing Prerequisites" for e in base["difficulty_explanations"])
    assert not any(e["title"] == "Missing Prerequisites" for e in everything["difficulty_explanations"])
    assert everything["paper_difficulty"]["explanation"].startswith("0 prerequisite concepts")


def test_the_http_known_field_updates_difficulty_the_same_way(tmp_path):
    path = _pdf(tmp_path)
    client = TestClient(app)
    with open(path, "rb") as handle:
        base = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["report"]
    with open(path, "rb") as handle:
        known = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")},
                            data={"known": [s["concept"] for s in base["learning_plan"]]}).json()["report"]
    assert known["paper_difficulty"]["score"] < base["paper_difficulty"]["score"]
    assert known["paper_difficulty"]["explanation"].startswith("0 prerequisite concepts")
