"""Display equations are rebuilt from the layout (the DPO loss, split into many text blocks), worked arithmetic inside sentences is not an equation, and equations keep their page."""
import pymupdf
import pytest

from backend.parsing.equation_extractor import is_prose_arithmetic, looks_like_prose
from backend.pipeline import ResearchPaperPipeline

pytestmark = pytest.mark.prereqai
PROSE = "We train the policy with the objective below and report the average reward over the held out comparisons in every experiment."


def test_arithmetic_inside_sentences_is_not_an_equation():
    for line in ["he travels for 3 * 6 = 18 miles. The", "was 125% * $40.00 = $50.00. The answer is", "$3.00 = $53.00. The answer is", "0.25 * $40.00 = $10.00. The delivery",
                 "500. 9 + 90(2) + 401(3) = 1392. The", "8 = 12.5% for “First choice” and 1 -6", "3 * 6 = 18 miles"]:
        assert looks_like_prose(line), line
    for line in ["L(θ) = -E[log σ(β r)]", "y = Softmax(TopK(x · Wg))", "G(x) := Softmax(TopK(x · Wg)),", "a = b + c", "f(x) = x^2"]:
        assert not is_prose_arithmetic(line) and not looks_like_prose(line), line


def _pdf(tmp_path):
    document = pymupdf.open()
    page = document.new_page()
    y = 72
    for _ in range(2):
        page.insert_text((72, y), PROSE, fontsize=9)
        y += 12
    pieces = [(150, 300, "LDPO(pT; pref) = -E(x,yw,yl)~D"), (290, 294, "log sigma"), (320, 288, "b log pT(yw | x)"), (320, 308, "pref(yw | x)"), (430, 300, "- b log pT(yl | x)"), (505, 300, "(7)")]
    for x, y2, text in pieces:
        page.insert_text((x, y2), text, fontsize=10)
    page.insert_text((72, 340), PROSE, fontsize=9)
    page.insert_text((72, 352), PROSE, fontsize=9)
    path = tmp_path / "eq.pdf"
    path.write_bytes(document.tobytes())
    return path


def test_a_display_equation_in_many_blocks_is_one_equation_with_its_page_and_number(tmp_path):
    paper = ResearchPaperPipeline().run(str(_pdf(tmp_path))).paper
    found = [e for e in paper.equations if "LDPO" in e.expression]
    assert len(found) == 1, [e.expression for e in paper.equations]
    equation = found[0]
    assert equation.page_number == 1 and equation.tag == "7" and "(7)" not in equation.expression
    for part in ["LDPO(pT; pref)", "log sigma", "b log pT(yw | x)", "pref(yw | x)", "b log pT(yl | x)"]:
        assert part in equation.expression, (part, equation.expression)
    assert equation.expression.index("LDPO") < equation.expression.index("log sigma") < equation.expression.index("(yl | x)")


def test_the_dpo_paper_loss_is_rebuilt_and_the_cot_papers_worked_arithmetic_is_not():
    dpo = ResearchPaperPipeline().run("backend/prereqai_eval/benchmark/pdfs/dpo.pdf").paper
    loss = next(e for e in dpo.equations if e.tag == "7")
    assert loss.page_number == 4 and loss.section.endswith("Direct Preference Optimization")
    for part in ["LDPO(πθ; πref)", "log σ", "πθ(yw | x)", "πref(yw | x)", "πθ(yl | x)", "πref(yl | x)"]:
        assert part in loss.expression, (part, loss.expression)
    chain = ResearchPaperPipeline().run("backend/prereqai_eval/benchmark/pdfs/chain-of-thought.pdf").paper
    assert not [e for e in chain.equations if "miles" in e.expression or "$" in e.expression]


def test_equations_still_link_to_the_concepts_of_their_section():
    from backend.platform import platform

    report = platform.analyze("backend/prereqai_eval/benchmark/pdfs/dpo.pdf")["report"]
    loss = next(e for e in report["equations"] if e.get("tag") == "7")
    assert loss["page_number"] == 4 and loss["concepts"], loss
