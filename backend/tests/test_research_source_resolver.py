from backend.ingestion import (
    ResearchSource,
    ResearchSourceResolver,
)


def test_pdf_resolution():

    resolver = ResearchSourceResolver()

    pdf_path = resolver.resolve(

        ResearchSource(
            source_type="pdf",
            identifier="papers/attention.pdf",
            original_input="papers/attention.pdf",
        )
    )

    assert pdf_path == "papers/attention.pdf"
