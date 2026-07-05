from backend.ingestion import (
    ResearchMetadataResolver,
)


def test_crossref_lookup():

    resolver = ResearchMetadataResolver()

    metadata = resolver.resolve_doi(
        "10.1038/s41586-020-2649-2"
    )

    assert metadata.doi == "10.1038/s41586-020-2649-2"

    assert metadata.title != ""
