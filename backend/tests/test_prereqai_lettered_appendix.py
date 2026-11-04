"""Section parser -> concept detector -> study plan: an appendix whose sections are lettered ("A Proofs", "B.1 Details") after
the References is paper content the learner must understand, not bibliography; its concepts reach the plan. Reference entries
(including a bare author line such as "A. Vaswani") stay out."""
import pymupdf as fitz
import pytest

from backend.platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai

FRONT = "A Paper\n\nAbstract\nWe study sorting.\n\n1 Introduction\nWe sort lists quickly.\n"


def _concepts(tmp_path, *pages):
    document = fitz.open()
    for text in pages:
        document.new_page().insert_text((72, 72), text, fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    outcome = PreReqAIPlatform().analyze(str(path))
    assert outcome["status"] == "success", outcome
    return {c["name"] if isinstance(c, dict) else c for c in outcome["report"]["concepts"]}


def test_a_lettered_appendix_after_the_references_is_analysed(tmp_path):
    names = _concepts(
        tmp_path,
        FRONT + "\nReferences\n[1] A. Vaswani. Graph attention networks.\n",
        "A Additional Proofs\nThe softmax gradient descent bound.\n\nB.1 Training Details\nWe use backpropagation.\n",
    )
    assert names == {"Softmax", "Gradient Descent", "Backpropagation"}


def test_reference_entries_and_author_lines_stay_out(tmp_path):
    names = _concepts(
        tmp_path,
        FRONT + "\nReferences\nA. Vaswani\nGraph attention networks. Diffusion models. Softmax.\n",
    )
    assert names == set()


def test_a_title_case_line_before_the_references_is_not_a_heading(tmp_path):
    names = _concepts(tmp_path, FRONT + "\nA Survey Of Softmax\nsoftmax everywhere.\n")
    assert "Softmax" in names
