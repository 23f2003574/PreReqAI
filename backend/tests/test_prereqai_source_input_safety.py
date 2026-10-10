"""A DOI containing '.'/'..' path segments must never reach the Crossref URL, where it would be resolved
to a different API endpoint; ordinary DOIs (including dots inside a segment) keep working."""
import pytest
import requests

from backend.ingestion.research_metadata_resolver import ResearchMetadataResolver
from backend.ingestion.research_source_detector import ResearchSourceDetector


@pytest.mark.parametrize("doi", ["10.1234/../../members", "10.1234/a/./b", "10.1234/..", "doi:10.1234/x/../../../works"])
def test_a_doi_with_dot_segments_is_not_a_supported_source(doi):
    with pytest.raises(ValueError, match="Unsupported research source"):
        ResearchSourceDetector().detect(doi)


@pytest.mark.parametrize("doi", ["10.1234/../../members", "10.1234/a/./b"])
def test_the_crossref_lookup_refuses_dot_segments_before_any_request(doi, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("a request was sent"))

    with pytest.raises(ValueError, match="Not a valid DOI"):
        ResearchMetadataResolver().resolve_doi(doi)


@pytest.mark.parametrize("text, doi", [("10.1145/3292500.3330701", "10.1145/3292500.3330701"),
                                       ("doi:10.1000/xyz.v1.2", "10.1000/xyz.v1.2"),
                                       ("https://doi.org/10.1038/s41586-020-2649-2", "10.1038/s41586-020-2649-2")])
def test_ordinary_dois_still_resolve(text, doi, monkeypatch):
    assert ResearchSourceDetector().detect(text).identifier == doi

    seen = []

    class _Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"title": ["A paper"], "URL": "https://example.org"}}

    monkeypatch.setattr(requests, "get", lambda url, timeout: seen.append(url) or _Reply())
    assert ResearchMetadataResolver().resolve_doi(doi).title == "A paper"
    assert seen == [ResearchMetadataResolver.CROSSREF_API + doi]
