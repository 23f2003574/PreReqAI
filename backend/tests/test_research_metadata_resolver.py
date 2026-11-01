import requests

from backend.ingestion.research_metadata_resolver import (
    ResearchMetadataResolver,
)


class _Reply:
    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"title": ["A Crossref Title"], "URL": "https://doi.org/10.1038/s41586-020-2649-2",
                            "publisher": "Springer Nature"}}


def test_crossref_lookup(monkeypatch):
    """Offline: the Crossref reply is faked, so the test needs no network."""

    requested = []
    monkeypatch.setattr(requests, "get", lambda url, timeout: requested.append(url) or _Reply())

    metadata = ResearchMetadataResolver().resolve_doi(
        "10.1038/s41586-020-2649-2"
    )

    assert requested == ["https://api.crossref.org/works/10.1038/s41586-020-2649-2"]

    assert metadata.doi == "10.1038/s41586-020-2649-2"

    assert metadata.title == "A Crossref Title"
    assert metadata.publisher == "Springer Nature"
