"""A saved plan resumed against a different paper still applies its progress but says so; the same paper gets no warning."""
import pymupdf
from starlette.testclient import TestClient

from backend.cli import main
from backend.main import app
from backend.study_plan_markdown import resume_mismatch_warning

SAMPLE = "examples/prerequisites/sample-paper.pdf"
PLAN = "# Study plan: Attention Is All You Need (PreReqAI sample paper)\n\n- [x] 1. Probability (~10h)\n"


def _other_paper(tmp_path):
    path = tmp_path / "other.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), "Abstract\nWe train neural networks with gradient descent.\n", fontsize=10)
    doc.save(path)
    return path


def test_warning_helper_compares_titles_loosely():
    assert resume_mismatch_warning(PLAN, "attention is  all you need (preReqAI sample paper)") is None
    assert "saved for 'Attention Is All You Need (PreReqAI sample paper)', not 'Other'" in resume_mismatch_warning(PLAN, "Other")
    assert resume_mismatch_warning("not a plan", "Other") is None


def test_cli_warns_when_the_plan_is_for_another_paper(tmp_path, capsys):
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    assert main(["prerequisites", "analyze", str(_other_paper(tmp_path)), "--resume", str(plan)]) == 0
    assert "warning: The resumed plan was saved for 'Attention Is All You Need" in capsys.readouterr().out
    assert main(["prerequisites", "analyze", SAMPLE, "--resume", str(plan)]) == 0
    assert "resumed plan was saved for" not in capsys.readouterr().out


def test_http_warns_when_the_plan_is_for_another_paper(tmp_path):
    client = TestClient(app)
    other = _other_paper(tmp_path).read_bytes()
    body = client.post("/api/prerequisites/analyze", files={"paper": ("o.pdf", other, "application/pdf"), "resume": ("plan.md", PLAN.encode(), "text/markdown")}).json()
    assert any("resumed plan was saved for" in w for w in body["warnings"])
    with open(SAMPLE, "rb") as handle:
        same = client.post("/api/prerequisites/analyze", files={"paper": ("s.pdf", handle, "application/pdf"), "resume": ("plan.md", PLAN.encode(), "text/markdown")}).json()
    assert not any("resumed plan" in w for w in same["warnings"])
