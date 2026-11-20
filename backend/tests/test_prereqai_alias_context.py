"""An alias that is also something else (a table column "CNN", the prompt "chunk size" of a long-context model) counts only with context cues nearby."""
from pathlib import Path

import pytest

from backend.concepts import RuleBasedConceptDetector
from backend.evidence import build_evidence
from backend.ingestion import DocumentMetadata
from backend.models import Paper, Paragraph

pytestmark = pytest.mark.prereqai
FILLER = "x " * 120


def _paper(*texts):
    paper = Paper(source_path="x.pdf", metadata=DocumentMetadata(title="T", author="A", subject="", keywords="", creator="", producer="", page_count=1))
    paper.paragraphs = [Paragraph(i, "3 Method", text) for i, text in enumerate(texts, start=1)]
    return paper


def _names(*texts):
    paper = _paper(*texts)
    RuleBasedConceptDetector().detect(paper)
    return {c.name: c.occurrences for c in paper.concepts}


def test_a_cnn_table_column_is_not_a_convolutional_network():
    assert "Convolutional Neural Network" not in _names("Model Tinfer Average CNN arXiv PubMed R1 R1 R1 MHA-Large 0.37 46.0 42.9 44.6 " + FILLER)
    assert "Convolutional Neural Network" not in _names("We evaluate on summarization datasets CNN/Daily Mail and arXiv. The CNN column of Table 1 reports ROUGE.")


def test_cnn_with_its_context_still_counts_and_the_full_name_always_does():
    assert _names("A CNN applies convolution filters over the image and pools the feature maps.")["Convolutional Neural Network"] == 1
    assert _names("CNNs with residual connections dominate image classification on ImageNet.")["Convolutional Neural Network"] == 1
    assert _names("A convolutional neural network is used. " + FILLER)["Convolutional Neural Network"] == 1
    mixed = _names("We use CNN/Daily Mail. " + FILLER + " Separately a CNN with 3x3 convolution kernels is trained.")
    assert mixed["Convolutional Neural Network"] == 1  # the dataset is excluded once, the real mention counts once


def test_chunk_size_needs_a_retrieval_context():
    assert "Document Chunking" not in _names("If the prompt is very large, we can chunk it into smaller pieces and pre-fill the cache. We select the window size as our chunk size.")
    assert "Document Chunking" in _names("For retrieval we split each document into passages; the chunk size trades recall against embedding cost.")
    assert "Document Chunking" in _names("We study chunking strategies. " + FILLER)  # the other aliases are not guarded


def test_evidence_names_the_matched_alias_and_its_context():
    paper = _paper("A CNN applies convolution filters over the image. " + FILLER)
    RuleBasedConceptDetector().detect(paper)
    from backend.ingestion import RawPage

    paper.pages = [RawPage(page_number=1, text=paper.paragraphs[0].content)]
    paper.paragraphs[0].page_number = 1
    passage = build_evidence(paper)["Convolutional Neural Network"][0]
    assert passage["matched_term"] == "CNN" and passage["context"].lower().startswith("convolution")


@pytest.mark.parametrize("name,concept", [("gqa", "Convolutional Neural Network"), ("mistral-7b", "Document Chunking")])
def test_the_held_out_papers_no_longer_detect_the_false_positives(name, concept):
    from backend.pipeline import ResearchPaperPipeline

    pdf = Path(f"backend/prereqai_eval/heldout/pdfs/{name}.pdf")
    if not pdf.exists():
        pytest.fail("the held-out PDFs are part of the repository")
    assert concept not in {c.name for c in ResearchPaperPipeline().run(str(pdf)).paper.concepts}
