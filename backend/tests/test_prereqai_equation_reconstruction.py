"""Layout-aware equation reconstruction: fractions from drawn bars, large-operator glyphs, numbered displays without an equals sign, and continuation clauses."""
import pymupdf
import pytest

from backend.ingestion import pdf_ingestion_engine as engine
from backend.parsing.equation_extractor import EquationExtractor

pytestmark = pytest.mark.prereqai


def _page():
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((60, 80), "The model is defined by the following display, which we use throughout.", fontsize=11)
    page.insert_text((100, 130), "p(y) =", fontsize=11)
    page.insert_text((150, 120), "exp(a)", fontsize=11)
    page.draw_line((148, 126), (200, 126), width=0.5)
    page.insert_text((148, 140), "exp(a) + exp(b)", fontsize=11)
    page.insert_text((300, 130), "(1)", fontsize=11)
    page.insert_text((100, 190), "max  E[r(x, y)] - beta KL(p || q)", fontsize=11)
    page.insert_text((300, 190), "(2)", fontsize=11)
    page.insert_text((100, 240), "where Z = exp(c) + exp(d)", fontsize=11)
    return document, page


def test_a_drawn_fraction_is_read_as_numerator_over_denominator():
    _, page = _page()
    groups = engine.equation_groups(page.get_text("dict")["blocks"], drawings=page.get_drawings)
    first = next(g for g in groups if g["tag"] == "1")
    assert "(exp(a))/(exp(a) + exp(b))" in first["text"].replace(" ", "") or "(exp(a))/(exp(a)+exp(b))" in first["text"].replace(" ", "")


def test_a_numbered_display_without_an_equals_sign_is_an_equation():
    _, page = _page()
    groups = engine.equation_groups(page.get_text("dict")["blocks"], drawings=page.get_drawings)
    assert any(g["tag"] == "2" and "max" in g["text"] for g in groups)


def test_large_operator_letters_of_the_extension_font_become_the_operator_signs():
    assert engine._span_text({"text": "P", "font": "CMEX10"}) == "Σ" and engine._span_text({"text": "P", "font": "CMR10"}) == "P"
    assert engine._span_text({"text": "Q", "font": "CMEX10"}) == "Π"


def test_a_where_clause_is_part_of_the_equation_it_defines():
    from types import SimpleNamespace

    sections = [SimpleNamespace(title="3 Method", content="Prose only.", page_number=1)]
    page = SimpleNamespace(page_number=1, equation_groups=[{"text": "p(y) = (a)/(b)", "tag": "1", "fragments": ["p(y) ="]}, {"text": "where Z = exp(c)", "tag": "", "fragments": ["where Z ="]}])
    paper = SimpleNamespace(pages=[page], sections=sections, equations=[])
    EquationExtractor().extract(paper)
    assert len(paper.equations) == 1 and paper.equations[0].expression.endswith("where Z = exp(c)")


def test_dpo_reference_pdf_recovers_the_tagged_equations():
    from backend.prereqai_eval import gate

    paper = gate._real_papers({"dpo"})["dpo"]
    tags = {int(e.tag) for e in paper.equations if e.tag.isdigit()}
    assert len(tags & set(range(1, 23))) >= 21
    first = next(e for e in paper.equations if e.tag == "1").expression.replace(" ", "")
    assert "(exp(r" in first and ")/(exp(r" in first  # numerator over denominator, not scrambled with a stray "+"
    assert "Σ" in " ".join(e.expression for e in paper.equations)
