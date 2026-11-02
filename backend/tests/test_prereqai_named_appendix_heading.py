"""A named appendix ("Appendix A: Proofs") starts its own section instead of being folded into the References before it."""
import pytest

from types import SimpleNamespace

from backend.parsing.scientific_section_parser import SECTION_PATTERN, ScientificSectionParser

pytestmark = pytest.mark.prereqai


def test_named_appendix_is_its_own_section_after_the_bibliography():
    text = ("1 Introduction\nWe study attention.\nReferences\n[1] Policy gradient methods.\n"
            "Appendix A: Proofs\nThe lemma follows from calculus.\nAppendix B. Additional Experiments\nMore runs.\n")
    paper = ScientificSectionParser().parse(SimpleNamespace(source_path="p.pdf", metadata=None, pages=[], full_text=text))
    assert [section.title for section in paper.sections] == [
        "1 Introduction", "References", "Appendix A: Proofs", "Appendix B. Additional Experiments"]
    assert "lemma" not in paper.sections[1].content


@pytest.mark.parametrize("line", [
    "Appendix A: we show that this holds.",         # a sentence, not a title
    "Appendix A shows the proofs of all lemmas.",
    "See Appendix A: Proofs for details.",
])
def test_sentences_mentioning_an_appendix_stay_body_text(line):
    assert SECTION_PATTERN.search(line) is None
