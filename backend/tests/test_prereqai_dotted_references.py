from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.ingestion.pdf_ingestion_engine import RawDocument, RawPage
from backend.parsing import ReferenceExtractor, ScientificSectionParser


def _references(text):
    document = RawDocument("p.pdf", DocumentMetadata("t", "a", "", "", "", "", 1), [RawPage(1, text)])
    paper = ReferenceExtractor().extract(ScientificSectionParser().parse(document))
    return [(r.reference_number, r.raw_text) for r in paper.references]


def test_a_bibliography_numbered_with_dots_is_extracted():
    text = "1 Introduction\nSee [1].\nReferences\n1. Vaswani A. Attention is all you need. NeurIPS 2017.\n2. Kipf T. Semi-supervised\nclassification. ICLR 2017.\n"
    assert _references(text) == [(1, "Vaswani A. Attention is all you need. NeurIPS 2017."), (2, "Kipf T. Semi-supervised classification. ICLR 2017.")]


def test_a_wrapped_line_starting_with_a_year_is_not_a_new_entry():
    text = "References\n1. Vaswani A. Attention is all you need. NeurIPS\n2017. Long Beach.\n2. Kipf T. GCN. ICLR 2017.\n"
    assert _references(text) == [(1, "Vaswani A. Attention is all you need. NeurIPS 2017. Long Beach."), (2, "Kipf T. GCN. ICLR 2017.")]


def test_bracketed_references_are_unchanged_and_take_precedence():
    assert _references("References\n[1] Smith. A paper.\n[2] Jones. Another.\n") == [(1, "Smith. A paper."), (2, "Jones. Another.")]


def test_unnumbered_or_out_of_sequence_lists_yield_nothing():
    assert _references("References\nVaswani A. Attention. 2017.\n5. Orphan entry.\n") == []
