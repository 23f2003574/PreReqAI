"""Direct PDF links: a controlled download (https by default, public addresses only, every redirect checked, size and time limits) whose
result is validated as a PDF and then goes through the ordinary PDF ingestion. The caching and atomic storage are the arXiv resolver's."""
import hashlib
import ipaddress
import os
import socket
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .arxiv_resolver import ArxivResolver
from .research_source_detector import ResearchSource

DEFAULT_MAX_MB = 50.0  # PREREQAI_PDF_URL_MAX_MB; far above a paper, it only stops a download from filling the disk or the memory
DEFAULT_TIMEOUT_SECONDS = 30.0  # PREREQAI_PDF_URL_TIMEOUT_SECONDS: per network read, and for the download as a whole
MAX_REDIRECTS = 5
CHUNK_BYTES = 64 * 1024
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class PdfUrlError(ValueError):
    """A direct PDF link that cannot be used. `kind`: invalid_url | blocked | timeout | too_large | failed | not_pdf; `hint` says what to do."""

    def __init__(self, kind, message, hint="", transient=False):
        super().__init__(message)
        self.kind, self.hint, self.transient = kind, hint, transient  # transient: a dropped connection or a busy server (429, 5xx), worth another attempt


def _positive(name, default):
    try:
        value = float(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value > 0 and value != float("inf") else default


def public_addresses(host, port, getaddrinfo=socket.getaddrinfo):
    """The addresses `host` resolves to, only if every one is a public one. Resolved once: the caller connects to these very addresses, so a
    second lookup by the HTTP client (DNS rebinding) can never lead somewhere else."""
    try:
        found = [info[4][0] for info in getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    except (socket.gaierror, UnicodeError) as error:
        raise PdfUrlError("failed", f"The host {host!r} could not be found.", "Check the link, or download the PDF and pass its path.") from error
    addresses = list(dict.fromkeys(address.split("%")[0] for address in found))
    for address in addresses:
        ip = ipaddress.ip_address(address)
        ip = ip.ipv4_mapped or ip if isinstance(ip, ipaddress.IPv6Address) else ip  # ::ffff:127.0.0.1 is loopback
        if not ip.is_global:
            raise PdfUrlError("blocked", f"The link points to a non-public address ({host}), which PreReqAI does not download from.",
                              "Only links on the public internet are fetched; download the PDF yourself and pass its path.")
    if not addresses:
        raise PdfUrlError("failed", f"The host {host!r} has no address.", "Check the link, or download the PDF and pass its path.")
    return addresses


def pinned_fetch(scheme, address, port, host, target, timeout):
    """GET `target` from `address` (already vetted) with the certificate and Host of `host`; no redirects, no proxies, no retries.
    Returns (status, headers, chunks, close)."""
    import urllib3

    wait = urllib3.Timeout(connect=timeout, read=timeout)
    if scheme == "https":
        pool = urllib3.HTTPSConnectionPool(address, port=port, timeout=wait, retries=False, cert_reqs="CERT_REQUIRED",
                                           assert_hostname=host, server_hostname=host)
    else:
        pool = urllib3.HTTPConnectionPool(address, port=port, timeout=wait, retries=False)
    response = pool.urlopen("GET", target, headers={"Host": host if port in (80, 443) else f"{host}:{port}", "User-Agent": "PreReqAI",
                                                    "Accept": "application/pdf,*/*;q=0.5"},
                            redirect=False, retries=False, preload_content=False)

    def close():
        response.release_conn()
        pool.close()

    return response.status, response.headers, response.stream(CHUNK_BYTES), close


class PdfUrlResolver(ArxivResolver):
    """Downloads a paper from a direct PDF link as a local PDF (cached under cache/pdf-url)."""

    CACHE_DIRECTORY = Path("cache/pdf-url")

    def __init__(self, max_bytes=None, timeout=None, allow_http=None, getaddrinfo=socket.getaddrinfo, fetch=pinned_fetch):
        super().__init__()
        self.max_bytes = max_bytes if max_bytes is not None else int(_positive("PREREQAI_PDF_URL_MAX_MB", DEFAULT_MAX_MB) * 1024 * 1024)
        self.timeout = timeout if timeout is not None else _positive("PREREQAI_PDF_URL_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        self.allow_http = allow_http if allow_http is not None else os.environ.get("PREREQAI_ALLOW_HTTP_PDF_URLS", "").strip() == "1"
        self._getaddrinfo, self._fetch = getaddrinfo, fetch

    def resolve(self, source: ResearchSource) -> str:
        pdf_path = self.cache_directory / (hashlib.sha256(source.identifier.encode()).hexdigest()[:32] + ".pdf")
        for candidate in (pdf_path, self._fallback_directory() / pdf_path.name):
            if self._is_cached_pdf(candidate):
                return str(candidate)
        content = self._download(source.identifier)
        self._validate(content)
        return str(self._store(pdf_path, content))

    def _download(self, url):  # noqa: C901 - one loop: vet the hop, fetch it, follow a redirect or read the body
        deadline = time.monotonic() + self.timeout
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlsplit(url)
            host = parts.hostname
            if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
                raise PdfUrlError("invalid_url", f"Not a usable PDF link: {url}", "Give a plain https link to the PDF, without a user name or password.")
            if parts.scheme == "http" and not self.allow_http:
                raise PdfUrlError("blocked", "Plain http links are not downloaded: the paper could be altered on the way.",
                                  "Use the https link, or set PREREQAI_ALLOW_HTTP_PDF_URLS=1 if you accept that risk on a trusted network.")
            try:
                port = parts.port or (443 if parts.scheme == "https" else 80)
            except ValueError as error:
                raise PdfUrlError("invalid_url", f"Not a usable PDF link: {url}", "Check the port in the link.") from error
            target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            addresses = public_addresses(host, port, self._getaddrinfo)
            reply = None
            for address in addresses:  # the vetted addresses only, in order, until one answers
                try:
                    reply = self._fetch(parts.scheme, address, port, host, target, self.timeout)
                    break
                except (TimeoutError, OSError, Exception) as error:  # noqa: B014 - urllib3 raises its own types
                    failure = error
            if reply is None:
                self._raise_network(failure)
            status, headers, chunks, close = reply
            try:
                if status in REDIRECT_STATUSES:
                    location = headers.get("Location")
                    if not location:
                        raise PdfUrlError("failed", f"The server redirected without saying where (HTTP {status}).", "Try again later, or pass the PDF's path.")
                    url = urljoin(url, location)  # checked as the next hop's own URL: scheme, host, addresses
                    continue
                if status != 200:
                    raise PdfUrlError("failed", f"The server refused to provide the PDF (HTTP {status}).", "Check the link, or download the PDF and pass its path.", transient=status in (429, 500, 502, 503, 504))
                declared = headers.get("Content-Length", "")
                if declared.isdigit() and int(declared) > self.max_bytes:
                    raise self._too_large()
                body = bytearray()
                try:
                    for chunk in chunks:
                        body += chunk
                        if len(body) > self.max_bytes:
                            raise self._too_large()
                        if time.monotonic() > deadline:
                            raise TimeoutError("the download took too long")
                except PdfUrlError:
                    raise
                except Exception as error:
                    self._raise_network(error)
                return bytes(body)
            finally:
                close()
        raise PdfUrlError("failed", "The link redirected too many times.", "Use the final link, or download the PDF and pass its path.")

    def _too_large(self):
        return PdfUrlError("too_large", f"The PDF is larger than the limit of {self.max_bytes} bytes.",
                           "Download it yourself and pass its path, or raise PREREQAI_PDF_URL_MAX_MB; nothing was kept.")

    @staticmethod
    def _raise_network(error):
        name = type(error).__name__
        if isinstance(error, TimeoutError) or "Timeout" in name:
            raise PdfUrlError("timeout", f"The download timed out: {error}", "Try again, or download the PDF and pass its path.") from error
        raise PdfUrlError("failed", f"The PDF could not be downloaded ({name}).", "Check the link and your connection, or pass the PDF's path.", transient=True) from error

    @classmethod
    def _validate(cls, content):
        """A PDF by its content, whatever the URL ends in or the server claims: the header, a complete ending, and a document the PDF library opens."""
        reason = None
        if not content.startswith(b"%PDF-"):
            reason = "the reply is not a PDF (it may be a web page or a login screen)"
        elif not cls._is_complete_pdf(content):
            reason = "the PDF is incomplete (the download was cut off)"
        else:
            try:
                import pymupdf

                with pymupdf.open(stream=content, filetype="pdf") as pdf:
                    if pdf.page_count < 1:
                        reason = "the PDF has no pages"
            except Exception:
                reason = "the PDF is damaged and cannot be read"
        if reason:
            raise PdfUrlError("not_pdf", f"The link did not give a usable PDF: {reason}.", "Check that the link points straight to the PDF file.")
