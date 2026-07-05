from backend.ingestion import (
    ResearchSource,
)

from backend.ingestion.arxiv_resolver import (
    ArxivResolver,
)


def test_arxiv_download():

    resolver = ArxivResolver()

    pdf = resolver.resolve(

        ResearchSource(
            source_type="arxiv",
            identifier="1706.03762",
            original_input="https://arxiv.org/abs/1706.03762",
        )
    )

    assert pdf.endswith(".pdf")
