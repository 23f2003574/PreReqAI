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
        DoiResolver, "_download_public", lambda self, url: fetched.append(url) or b"%PDF-1.4 data\n%%EOF"
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


def _reply(status=200, headers=None, chunks=(b"%PDF-1.4 ok\n%%EOF",)):
    return status, headers or {}, iter(chunks), lambda: None


def _crossref_to(monkeypatch, url="https://x.org/p.pdf"):
    monkeypatch.setattr("backend.ingestion.doi_resolver.requests.get", lambda u, timeout, **kw: crossref([{"URL": url, "content-type": "application/pdf"}]))


def test_a_redirect_to_an_internal_address_is_refused_after_a_public_first_hop(cached, monkeypatch):
    monkeypatch.setattr(
        "backend.ingestion.doi_resolver.socket.getaddrinfo",
        lambda host, port, type=None: [(2, 1, 6, "", ("127.0.0.1" if host == "localhost" else "93.184.216.34", port))],
    )
    _crossref_to(monkeypatch)
    monkeypatch.setattr(DoiResolver, "_fetch", staticmethod(lambda *a: _reply(302, {"Location": "https://localhost/secret.pdf"})))
    with pytest.raises(ValueError, match="public https address"):
        DoiResolver().resolve(doi_source("10.1234/redirect"))


def test_a_public_pdf_link_is_downloaded_through_a_redirect(cached, monkeypatch):
    _resolves_to(monkeypatch, "93.184.216.34")
    _crossref_to(monkeypatch)
    hops = []

    def fetch(scheme, address, port, host, target, timeout):
        hops.append((address, host, target))
        return _reply(302, {"Location": "/real.pdf"}) if target == "/p.pdf" else _reply()

    monkeypatch.setattr(DoiResolver, "_fetch", staticmethod(fetch))
    assert open(DoiResolver().resolve(doi_source("10.1234/ok")), "rb").read() == b"%PDF-1.4 ok\n%%EOF"
    assert hops == [("93.184.216.34", "x.org", "/p.pdf"), ("93.184.216.34", "x.org", "/real.pdf")]  # connected to the vetted address, with the host name kept for TLS and Host


def test_dns_rebinding_cannot_redirect_the_download(cached, monkeypatch):
    """The name is looked up once: the connection goes to the vetted public address even if a second lookup would answer with an internal one."""
    answers = iter(["93.184.216.34", "127.0.0.1", "127.0.0.1", "127.0.0.1"])
    monkeypatch.setattr("backend.ingestion.doi_resolver.socket.getaddrinfo", lambda host, port, type=None: [(2, 1, 6, "", (next(answers), port))])
    _crossref_to(monkeypatch)
    seen = []
    monkeypatch.setattr(DoiResolver, "_fetch", staticmethod(lambda scheme, address, *a: seen.append(address) or _reply()))
    DoiResolver().resolve(doi_source("10.1234/rebind"))
    assert seen == ["93.184.216.34"]


def test_an_oversized_body_is_refused_while_streaming(cached, monkeypatch):
    _resolves_to(monkeypatch, "93.184.216.34")
    _crossref_to(monkeypatch)
    big = (b"x" * 600 for _ in range(10))
    monkeypatch.setattr(DoiResolver, "_fetch", staticmethod(lambda *a: _reply(chunks=big)))
    monkeypatch.setenv("PREREQAI_PDF_URL_MAX_MB", "0.001")
    with pytest.raises(ValueError, match="larger than the limit"):
        DoiResolver().resolve(doi_source("10.1234/big"))


def test_a_download_that_never_finishes_is_stopped_by_the_deadline(cached, monkeypatch):
    import time

    _resolves_to(monkeypatch, "93.184.216.34")
    _crossref_to(monkeypatch)
    monkeypatch.setenv("PREREQAI_PDF_URL_TIMEOUT_SECONDS", "0.05")

    def slow():
        while True:
            time.sleep(0.03)
            yield b"x"

    monkeypatch.setattr(DoiResolver, "_fetch", staticmethod(lambda *a: _reply(chunks=slow())))
    with pytest.raises(ValueError, match="timed out|too long|took"):
        DoiResolver().resolve(doi_source("10.1234/slow"))
