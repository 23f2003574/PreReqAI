"""PREREQAI_CACHE_DIR gives downloads one fixed cache: the same paper is found whatever directory the command runs from, for
arXiv and DOI alike; unset or blank keeps the cache/ folder in the current directory."""
import pytest
import requests

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.ingestion.doi_resolver import DoiResolver
from backend.ingestion.research_source_detector import ResearchSource

pytestmark = pytest.mark.prereqai

PDF = b"%PDF-1.4 cached\n%%EOF"
ARXIV = ResearchSource(source_type="arxiv", identifier="1706.03762", original_input="arXiv:1706.03762")
DOI = ResearchSource(source_type="doi", identifier="10.1234/abc", original_input="10.1234/abc")


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a cached paper must not be downloaded again")

    monkeypatch.setattr(requests, "get", refuse)


@pytest.mark.parametrize("resolver, source, folder, name", [
    (ArxivResolver, ARXIV, "arxiv", "1706.03762.pdf"),
    (DoiResolver, DOI, "doi", "10.1234_abc.pdf"),
])
def test_the_configured_cache_is_found_from_any_working_directory(resolver, source, folder, name, tmp_path, monkeypatch, no_network):
    cache = tmp_path / "shared"
    (cache / folder).mkdir(parents=True)
    (cache / folder / name).write_bytes(PDF)
    monkeypatch.setenv("PREREQAI_CACHE_DIR", str(cache))

    for elsewhere in ("one", "two"):
        (tmp_path / elsewhere).mkdir()
        monkeypatch.chdir(tmp_path / elsewhere)
        assert resolver().resolve(source) == str(cache / folder / name)


def test_a_new_download_is_stored_under_the_configured_cache(tmp_path, monkeypatch):
    class Reply:
        content = PDF

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda url, timeout: Reply())
    monkeypatch.setenv("PREREQAI_CACHE_DIR", str(tmp_path / "shared"))
    monkeypatch.chdir(tmp_path)

    assert ArxivResolver().resolve(ARXIV) == str(tmp_path / "shared" / "arxiv" / "1706.03762.pdf")
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_unset_or_blank_keeps_the_cache_folder_in_the_working_directory(value, tmp_path, monkeypatch):
    monkeypatch.delenv("PREREQAI_CACHE_DIR", raising=False)
    if value is not None:
        monkeypatch.setenv("PREREQAI_CACHE_DIR", value)
    assert ArxivResolver().cache_directory.as_posix() == "cache/arxiv"
    assert DoiResolver().cache_directory.as_posix() == "cache/doi"


def test_a_tilde_is_expanded_and_an_explicit_cache_directory_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PREREQAI_CACHE_DIR", "~/papers")
    assert ArxivResolver().cache_directory == tmp_path / "papers" / "arxiv"

    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "explicit")
    assert ArxivResolver().cache_directory == tmp_path / "explicit"
