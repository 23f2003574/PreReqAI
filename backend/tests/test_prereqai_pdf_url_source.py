"""A direct PDF link is downloaded under SSRF, size, time and content checks, then analysed by the ordinary pipeline; DOI and arXiv are unchanged."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from backend.ingestion.pdf_url_resolver import PdfUrlError, PdfUrlResolver, pinned_fetch, public_addresses
from backend.ingestion.research_source_detector import ResearchSource, ResearchSourceDetector
from backend.platform import platform

pytestmark = pytest.mark.prereqai
SAMPLE = Path("examples/prerequisites/sample-paper.pdf").read_bytes()
URL = "https://papers.example.org/paper.pdf"
PUBLIC = lambda host, port, **kw: [(0, 0, 0, "", ("93.184.216.34", port))]  # noqa: E731


def source(url=URL):
    return ResearchSource("pdf_url", url, url)


def reply(status=200, body=SAMPLE, headers=None):
    return status, dict(headers or {}), iter([body[i:i + 4096] for i in range(0, len(body), 4096)] or [b""]), lambda: None


class Fetcher:
    """Stands in for the network: serves canned replies by URL path and records what it was asked for."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, scheme, address, port, host, target, timeout):
        self.calls.append((scheme, address, host, target))
        return self.replies.pop(0)


def resolver(fetcher, tmp_path, monkeypatch, **options):
    monkeypatch.setenv("PREREQAI_CACHE_DIR", str(tmp_path))
    return PdfUrlResolver(getaddrinfo=options.pop("getaddrinfo", PUBLIC), fetch=fetcher, **options)


def failure(call):
    with pytest.raises(PdfUrlError) as caught:
        call()
    return caught.value


def test_a_direct_link_is_detected_without_trusting_its_extension_and_other_inputs_are_unchanged():
    detect = ResearchSourceDetector().detect
    assert detect("https://openreview.net/pdf?id=abc123").source_type == "pdf_url"
    assert detect("https://aclanthology.org/2020.acl-main.1.pdf").source_type == "pdf_url"
    assert detect("https://arxiv.org/abs/1706.03762").source_type == "arxiv" and detect("10.1145/3292500.3330701").source_type == "doi"
    for bad in ("ftp://example.org/p.pdf", "https:///nohost", "see https://example.org/p.pdf now"):
        with pytest.raises(ValueError, match="Unsupported research source"):
            detect(bad)


def test_a_valid_pdf_is_downloaded_validated_cached_and_reaches_the_pdf_pipeline(tmp_path, monkeypatch):
    fetcher = Fetcher(reply(headers={"Content-Type": "text/html"}))  # the header is not trusted either way
    path = resolver(fetcher, tmp_path, monkeypatch).resolve(source())
    assert Path(path).read_bytes() == SAMPLE and fetcher.calls == [("https", "93.184.216.34", "papers.example.org", "/paper.pdf")]
    again = Fetcher()
    assert resolver(again, tmp_path, monkeypatch).resolve(source()) == path and again.calls == []  # cached: no second download
    outcome = platform.analyze(path)  # the existing ingestion, concepts and plan
    assert outcome["status"] == "success" and outcome["report"]["learning_plan"]


def test_through_the_platform_a_link_is_resolved_by_the_pdf_url_resolver(monkeypatch, tmp_path):
    fetcher = Fetcher(reply())
    monkeypatch.setitem(platform.analysis.source_resolver._resolvers, "pdf_url", resolver(fetcher, tmp_path, monkeypatch))
    outcome = platform.analyze(URL)
    assert outcome["status"] == "success" and fetcher.calls[0][2] == "papers.example.org"


@pytest.mark.parametrize("body,fragment", [(b"<html>please log in</html>", "not a PDF"), (SAMPLE[:700], "incomplete"),
                                           (b"%PDF-1.4\n" + b"garbage" * 50 + b"\n%%EOF\n", "damaged")])
def test_non_pdf_truncated_and_malformed_content_is_rejected(tmp_path, monkeypatch, body, fragment):
    error = failure(lambda: resolver(Fetcher(reply(body=body)), tmp_path, monkeypatch).resolve(source()))
    assert error.kind == "not_pdf" and fragment in str(error) and error.hint
    assert not list(tmp_path.rglob("*.pdf"))  # nothing cached


@pytest.mark.parametrize("host,address", [("localhost", "127.0.0.1"), ("internal.example", "10.1.2.3"), ("meta.example", "169.254.169.254"),
                                          ("v6.example", "::1"), ("mapped.example", "::ffff:127.0.0.1"), ("ula.example", "fd00::1")])
def test_private_loopback_and_link_local_destinations_are_blocked_before_any_request(tmp_path, monkeypatch, host, address):
    fetcher = Fetcher(reply())
    lookup = lambda h, p, **kw: [(0, 0, 0, "", (address, p))]  # noqa: E731
    error = failure(lambda: resolver(fetcher, tmp_path, monkeypatch, getaddrinfo=lookup).resolve(source(f"https://{host}/p.pdf")))
    assert error.kind == "blocked" and fetcher.calls == []


def test_one_private_address_among_public_ones_blocks_the_host_and_literals_are_checked():
    mixed = lambda h, p, **kw: [(0, 0, 0, "", ("93.184.216.34", p)), (0, 0, 0, "", ("192.168.0.9", p))]  # noqa: E731
    assert failure(lambda: public_addresses("rebind.example", 443, mixed)).kind == "blocked"
    assert failure(lambda: public_addresses("127.0.0.1", 443)).kind == "blocked"


def test_the_connection_uses_the_vetted_address_so_dns_rebinding_cannot_change_the_destination(tmp_path, monkeypatch):
    lookups, fetcher = [], Fetcher(reply())

    def rebinding(host, port, **kw):  # a hostile DNS server: public the first time, internal afterwards
        lookups.append(host)
        return [(0, 0, 0, "", ("93.184.216.34" if len(lookups) == 1 else "127.0.0.1", port))]

    resolver(fetcher, tmp_path, monkeypatch, getaddrinfo=rebinding).resolve(source())
    assert len(lookups) == 1 and fetcher.calls[0][1] == "93.184.216.34"  # one lookup, and the request went to its result


def test_a_redirect_to_an_internal_address_is_blocked_and_a_safe_redirect_is_followed(tmp_path, monkeypatch):
    hosts = {"papers.example.org": "93.184.216.34", "evil.example": "169.254.169.254", "cdn.example.org": "93.184.216.35"}
    lookup = lambda h, p, **kw: [(0, 0, 0, "", (hosts[h], p))]  # noqa: E731
    fetcher = Fetcher(reply(302, b"", {"Location": "https://evil.example/latest/meta-data"}))
    error = failure(lambda: resolver(fetcher, tmp_path, monkeypatch, getaddrinfo=lookup).resolve(source()))
    assert error.kind == "blocked" and [call[2] for call in fetcher.calls] == ["papers.example.org"]  # the internal hop was never requested
    ok = Fetcher(reply(301, b"", {"Location": "https://cdn.example.org/files/p.pdf"}), reply())
    assert Path(resolver(ok, tmp_path, monkeypatch, getaddrinfo=lookup).resolve(source("https://papers.example.org/other.pdf"))).exists()
    assert [call[3] for call in ok.calls] == ["/other.pdf", "/files/p.pdf"]
    downgrade = Fetcher(reply(302, b"", {"Location": "http://cdn.example.org/p.pdf"}))
    assert failure(lambda: resolver(downgrade, tmp_path, monkeypatch, getaddrinfo=lookup).resolve(source("https://papers.example.org/x.pdf"))).kind == "blocked"
    loop = Fetcher(*[reply(302, b"", {"Location": "https://papers.example.org/again"}) for _ in range(7)])
    assert "too many" in str(failure(lambda: resolver(loop, tmp_path, monkeypatch, getaddrinfo=lookup).resolve(source("https://papers.example.org/y.pdf"))))


def test_plain_http_is_refused_unless_explicitly_allowed_and_credentials_in_the_link_are_refused(tmp_path, monkeypatch):
    error = failure(lambda: resolver(Fetcher(reply()), tmp_path, monkeypatch).resolve(source("http://papers.example.org/p.pdf")))
    assert error.kind == "blocked" and "PREREQAI_ALLOW_HTTP_PDF_URLS" in error.hint
    allowed = Fetcher(reply())
    assert Path(resolver(allowed, tmp_path, monkeypatch, allow_http=True).resolve(source("http://papers.example.org/p.pdf"))).exists()
    assert allowed.calls[0][0] == "http"
    assert failure(lambda: resolver(Fetcher(reply()), tmp_path, monkeypatch).resolve(source("https://user:pw@papers.example.org/p.pdf"))).kind == "invalid_url"


def test_the_size_limit_is_enforced_from_the_header_and_while_streaming(tmp_path, monkeypatch):
    declared = Fetcher(reply(headers={"Content-Length": str(10 * 1024 * 1024)}))
    assert failure(lambda: resolver(declared, tmp_path, monkeypatch, max_bytes=1024 * 1024).resolve(source())).kind == "too_large"
    streamed = Fetcher(reply())  # no Content-Length: counted as it arrives
    assert failure(lambda: resolver(streamed, tmp_path, monkeypatch, max_bytes=1000).resolve(source())).kind == "too_large"


def test_timeouts_failed_downloads_and_bad_status_have_their_own_clear_errors(tmp_path, monkeypatch):
    def slow(*args):
        raise TimeoutError("read timed out")

    assert failure(lambda: resolver(slow, tmp_path, monkeypatch).resolve(source())).kind == "timeout"

    def refused(*args):
        raise ConnectionRefusedError()

    assert failure(lambda: resolver(refused, tmp_path, monkeypatch).resolve(source())).kind == "failed"
    assert "HTTP 404" in str(failure(lambda: resolver(Fetcher(reply(404, b"")), tmp_path, monkeypatch).resolve(source())))
    clock = iter([0.0, 100.0, 200.0, 300.0])
    monkeypatch.setattr("backend.ingestion.pdf_url_resolver.time.monotonic", lambda: next(clock))
    assert failure(lambda: resolver(Fetcher(reply()), tmp_path, monkeypatch, timeout=5).resolve(source())).kind == "timeout"  # the whole download is bounded too
    unknown = lambda h, p, **kw: (_ for _ in ()).throw(__import__("socket").gaierror("no such host"))  # noqa: E731
    assert failure(lambda: resolver(Fetcher(reply()), tmp_path, monkeypatch, getaddrinfo=unknown).resolve(source())).kind == "failed"


def test_the_platform_reports_each_failure_kind_with_its_status_and_hint(monkeypatch, tmp_path):
    def run(fetcher, **options):
        monkeypatch.setitem(platform.analysis.source_resolver._resolvers, "pdf_url", resolver(fetcher, tmp_path, monkeypatch, **options))
        return platform.analyze(URL)

    assert run(Fetcher(reply(body=b"<html>")))["status"] == "failure" and run(Fetcher(reply(body=b"<html>")))["hint"]
    assert run(Fetcher(reply()), max_bytes=100)["status"] == "limit_exceeded"
    assert run(lambda *a: (_ for _ in ()).throw(TimeoutError("slow")))["status"] == "timeout"
    blocked = run(Fetcher(reply()), getaddrinfo=lambda h, p, **kw: [(0, 0, 0, "", ("10.0.0.1", p))])
    assert blocked["status"] == "failure" and "non-public" in blocked["detail"]


def test_the_real_fetch_sends_the_host_header_to_the_pinned_address_and_does_not_follow_redirects():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["host"], seen["path"] = self.headers["Host"], self.path
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/secret")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        status, headers, chunks, close = pinned_fetch("http", "127.0.0.1", server.server_port, "papers.example.org", "/a.pdf?x=1", 5)
        close()
    finally:
        server.shutdown()
    assert status == 302 and headers["Location"].endswith("/secret")  # reported to the caller, never followed
    assert seen == {"host": f"papers.example.org:{server.server_port}", "path": "/a.pdf?x=1"}


def test_the_http_route_accepts_a_direct_link_and_doi_and_arxiv_keep_their_resolvers(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import app

    fetcher = Fetcher(reply())
    monkeypatch.setitem(platform.analysis.source_resolver._resolvers, "pdf_url", resolver(fetcher, tmp_path, monkeypatch))
    response = TestClient(app).post("/api/prerequisites/analyze", data={"source": URL})
    assert response.status_code == 200 and response.json()["status"] == "success"
    refused = TestClient(app).post("/api/prerequisites/analyze", data={"source": "ftp://example.org/p.pdf"})
    assert refused.status_code == 422 and "direct https link" in refused.json()["detail"]
    from backend.ingestion.research_source_resolver import ResearchSourceResolver
    names = {kind: type(item).__name__ for kind, item in ResearchSourceResolver()._resolvers.items()}
    assert names["doi"] == "DoiResolver" and names["arxiv"] == "ArxivResolver" and names["pdf"] == "PDFResolver"
