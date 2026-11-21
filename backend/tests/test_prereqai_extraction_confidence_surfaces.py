"""Extraction confidence on real generated PDFs (single column, two columns, footnotes) and through the API and the command line."""
import json

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer

from backend.cli import main
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)
STYLES = getSampleStyleSheet()
BODY = ("The Transformer uses self-attention and a softmax over the scores of every token in the sequence, and gradient descent trains the network with backpropagation. " * 4)


def build(path, columns=1, footnotes=False):
    document = BaseDocTemplate(str(path), pagesize=A4)
    width, height = A4
    gap = 20
    frames = [Frame(40, 60, (width - 80 - gap * (columns - 1)) / columns, height - 120, id=f"c{i}") for i in range(columns)]
    if columns == 2:
        frames = [Frame(40, 60, (width - 100) / 2, height - 120, id="left"), Frame(60 + (width - 100) / 2, 60, (width - 100) / 2, height - 120, id="right")]
    document.addPageTemplates([PageTemplate(id="p", frames=frames)])
    story = [Paragraph("Abstract", STYLES["Heading2"]), Paragraph(BODY, STYLES["BodyText"])]
    for title in ("1 Introduction", "2 Method", "3 Experiments", "4 Conclusion"):
        story += [Paragraph(title, STYLES["Heading2"]), Paragraph(BODY, STYLES["BodyText"]), Spacer(1, 6), Paragraph(BODY + " (Vaswani et al., 2017) [1]", STYLES["BodyText"])]
        if footnotes:
            story.append(Paragraph("<font size=7>1. A footnote about the experimental setup.</font>", STYLES["BodyText"]))
    story += [Paragraph("References", STYLES["Heading2"])] + [Paragraph(f"[{i}] Author {i}. A paper title. 20{10 + i}.", STYLES["BodyText"]) for i in range(1, 6)]
    document.build(story)
    return str(path)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


@pytest.mark.parametrize("name, options", [("single", {}), ("two-column", {"columns": 2}), ("footnotes", {"footnotes": True})])
def test_well_formed_layouts_report_a_trustworthy_text_layer_and_no_text_warnings(env, name, options):
    outcome = platform.analyze(build(env / f"{name}.pdf", **options))
    report = outcome["output"]["report"]["extraction_confidence"] if "output" in outcome else outcome["report"]["extraction_confidence"]
    statuses = {s["name"]: s["status"] for s in report["signals"]}
    assert statuses["text_layer"] == "ok" and statuses["ocr"] == "ok" and statuses["headings"] in ("ok", "warn") and len(report["signals"]) == 7
    assert not any(w.startswith("Extraction confidence is low") for w in outcome["warnings"]), outcome["warnings"]


def test_the_api_and_the_command_line_carry_the_confidence(env, capsys):
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        body = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    confidence = body["output"]["report"]["extraction_confidence"]
    assert confidence["level"] in ("high", "medium", "low") and len(confidence["signals"]) == 7 and all({"name", "status", "detail", "action"} <= set(s) for s in confidence["signals"])
    assert main(["prerequisites", "analyze", "examples/prerequisites/sample-paper.pdf", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["output"]["report"]["extraction_confidence"]["level"] == confidence["level"]
