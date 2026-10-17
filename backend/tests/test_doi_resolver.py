import pytest

from backend.ingestion import ResearchSource
from backend.ingestion.doi_resolver import DoiResolver
from backend.ingestion.research_source_resolver import ResearchSourceResolver


def doi_source(doi):
    return ResearchSource(source_type="doi", identifier=doi, original_input=doi)


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self._payload, self.content = payload, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def crossref(links):
    return FakeResponse({"message": {"link": links}})


@pytest.fixture
def cached(tmp_path, monkeypatch):
    monkeypatch.setattr(DoiResolver, "CACHE_DIRECTORY", tmp_path / "doi")
    return tmp_path


def test_doi_downloads_listed_pdf_and_caches_it(cached, monkeypatch):
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.requests.get",
        lambda url, timeout: crossref([
            {"URL": "https://x.org/landing", "content-type": "text/html"},
            {"URL": "https://x.org/p.pdf", "content-type": "application/pdf"},
        ]),
    )
    fetched = []
    monkeypatch.setattr(
        DoiResolver, "_download_public", lambda self, url: fetched.append(url) or b"%PDF-1.4 data"
    )

    path = DoiResolver().resolve(doi_source("10.1234/abc"))

    assert fetched == ["https://x.org/p.pdf"]
    assert path.endswith("10.1234_abc.pdf") and open(path, "rb").read().startswith(b"%PDF")
    assert DoiResolver().resolve(doi_source("10.1234/abc")) == path
    assert len(fetched) == 1


def test_doi_without_open_pdf_fails_clearly(cached, monkeypatch):
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.requests.get", lambda url, timeout: crossref([])
    )
    with pytest.raises(ValueError, match="No open PDF"):
        DoiResolver().resolve(doi_source("10.1234/closed"))


def test_doi_returning_non_pdf_is_not_cached(cached, monkeypatch):
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.requests.get",
        lambda url, timeout: crossref([{"URL": "https://x.org/p", "content-type": "application/pdf"}]),
    )
    monkeypatch.setattr(DoiResolver, "_download_public", lambda self, url: b"<html>")
    with pytest.raises(ValueError, match="did not return a PDF"):
        DoiResolver().resolve(doi_source("10.1234/html"))
    assert not list((cached / "doi").glob("*"))


def test_arxiv_doi_uses_arxiv_resolver(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.ArxivResolver.resolve",
        lambda self, source: seen.append(source) or "cache/arxiv/x.pdf",
    )
    assert DoiResolver().resolve(doi_source("10.48550/arXiv.1706.03762")) == "cache/arxiv/x.pdf"
    assert seen[0].source_type == "arxiv" and seen[0].identifier == "1706.03762"


def test_source_resolver_dispatches_doi(monkeypatch):
    monkeypatch.setattr(DoiResolver, "resolve", lambda self, source: "p.pdf")
    assert ResearchSourceResolver().resolve(doi_source("10.1234/abc")) == "p.pdf"


def _resolves_to(monkeypatch, *addresses):
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.socket.getaddrinfo",
        lambda host, port, type=None: [(2, 1, 6, "", (a, port)) for a in addresses],
    )


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"])
def test_a_pdf_link_to_an_internal_address_is_never_fetched(cached, monkeypatch, address):
    _resolves_to(monkeypatch, address)
    fetched = []
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.requests.get",
        lambda url, timeout, allow_redirects=True: fetched.append(url) or crossref(
            [{"URL": "https://internal.example/p.pdf", "content-type": "application/pdf"}]
        ),
    )
    with pytest.raises(ValueError, match="public https address"):
        DoiResolver().resolve(doi_source("10.1234/internal"))
    assert fetched == ["https://api.crossref.org/works/10.1234/internal"]


def test_a_redirect_to_an_internal_address_is_refused_after_a_public_first_hop(cached, monkeypatch):
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.socket.getaddrinfo",
        lambda host, port, type=None: [(2, 1, 6, "", ("127.0.0.1" if host == "localhost" else "93.184.216.34", port))],
    )

    class Redirect:
        is_redirect, headers = True, {"Location": "https://localhost/secret.pdf"}

    def get(url, timeout, allow_redirects=True):
        return Redirect() if url == "https://x.org/p.pdf" else crossref(
            [{"URL": "https://x.org/p.pdf", "content-type": "application/pdf"}]
        )

    monkeypatch.setattr("backend.ingestion.doi_resolver.requests.get", get)
    with pytest.raises(ValueError, match="public https address"):
        DoiResolver().resolve(doi_source("10.1234/redirect"))


def test_a_public_pdf_link_is_downloaded_through_a_redirect(cached, monkeypatch):
    _resolves_to(monkeypatch, "93.184.216.34")

    class Redirect:
        is_redirect, headers = True, {"Location": "/real.pdf"}

    class Pdf(FakeResponse):
        is_redirect = False

    def get(url, timeout, allow_redirects=True):
        if url.endswith("/works/10.1234/ok"):
            return crossref([{"URL": "https://x.org/p.pdf", "content-type": "application/pdf"}])
        return Redirect() if url == "https://x.org/p.pdf" else Pdf(content=b"%PDF-1.4 ok")

    monkeypatch.setattr("backend.ingestion.doi_resolver.requests.get", get)
    assert open(DoiResolver().resolve(doi_source("10.1234/ok")), "rb").read() == b"%PDF-1.4 ok"
