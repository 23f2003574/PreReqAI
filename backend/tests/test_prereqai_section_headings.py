"""Section detection recognises roman/lettered numbering and the headings real papers use beyond the classic IMRaD set."""
from types import SimpleNamespace

from backend.parsing.scientific_section_parser import ScientificSectionParser


def _titles(text):
    document = SimpleNamespace(full_text=text, source_path="p.pdf", metadata=None, pages=[])
    return [section.title for section in ScientificSectionParser().parse(document).sections]


def test_ieee_roman_numbered_and_lettered_appendix_headings_are_sections():
    text = ("Title\nI. INTRODUCTION\nWe study attention.\nII. RELATED WORK\nPrior work.\nIII. Model Architecture\nEncoder.\n"
            "A Appendix\nExtra.\nA.1 Ablation Study\nDetails.\n")
    assert _titles(text) == ["Front Matter", "I. INTRODUCTION", "II. RELATED WORK", "III. Model Architecture", "A Appendix", "A.1 Ablation Study"]


def test_unnumbered_modern_headings_are_sections():
    text = "Abstract\nShort.\nPreliminaries\nNotation.\nLimitations\nNone.\nAcknowledgements\nThanks.\nConclusion and Future Work\nDone.\n"
    assert _titles(text) == ["Abstract", "Preliminaries", "Limitations", "Acknowledgements", "Conclusion and Future Work"]


def test_heading_words_inside_sentences_and_lettered_sentences_are_not_headings():
    text = "Introduction\nIn this Model we run an Analysis of results.\nB This is a sentence about methods\nThe Evaluation was long.\n"
    assert _titles(text) == ["Introduction"]
