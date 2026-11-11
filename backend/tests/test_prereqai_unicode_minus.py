from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.ingestion.text_cleaning import clean_pdf_text
from backend.models import Paper, Paragraph


def test_the_mathematical_minus_sign_reads_as_a_hyphen():
    assert clean_pdf_text("Q−learning") == "Q-learning"


def test_a_concept_written_with_a_minus_sign_is_detected():
    paper = Paper(source_path="p.pdf", metadata=None, pages=[], sections=[])
    paper.paragraphs = [Paragraph(paragraph_id=1, section_title="Introduction", content="We apply Q−learning here.")]
    RuleBasedConceptDetector().detect(paper)
    assert "Q-Learning" in {concept.name for concept in paper.concepts}
