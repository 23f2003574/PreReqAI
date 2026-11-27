import ipaddress
import re
import socket
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

from .arxiv_resolver import ArxivResolver

from .research_source_detector import (
    ResearchSource,
)

ARXIV_DOI_PATTERN = re.compile(
    r"10\.48550/arxiv\.([0-9]+\.[0-9]+(?:v[0-9]+)?)",
    re.IGNORECASE,
)


def is_public_https_url(url: str) -> bool:
    """Whether `url` is an https URL whose host resolves only to public addresses. The PDF link comes from
    third-party metadata (and a DOI can arrive over HTTP), so the server must not be steered to loopback,
    private, link-local or otherwise internal addresses."""

    parts = urlsplit(url)

    if parts.scheme != "https" or not parts.hostname:

        return False

    try:

        addresses = {info[4][0] for info in socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)}

    except (socket.gaierror, UnicodeError):

        return False

    return bool(addresses) and all(ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses)


class DoiResolver(ArxivResolver):
    """
    Downloads the open PDF behind a DOI as a local PDF.

    An arXiv DOI is resolved as the arXiv paper; any other DOI is looked up
    in Crossref for a publisher-listed PDF link. A DOI with no such link
    fails with a clear message instead of a download of the landing page.
    """

    CACHE_DIRECTORY = Path("cache/doi")

    CROSSREF_API = "https://api.crossref.org/works/"

    def resolve(
        self,
        source: ResearchSource,
    ) -> str:

        arxiv_match = ARXIV_DOI_PATTERN.fullmatch(source.identifier)

        if arxiv_match:

            return ArxivResolver().resolve(
                ResearchSource(
                    source_type="arxiv",
                    identifier=arxiv_match.group(1),
                    original_input=source.original_input,
                )
            )

        pdf_path = (
            self.cache_directory /
            f"{source.identifier.replace('/', '_')}.pdf"
        )

        for candidate in (pdf_path, self._fallback_directory() / pdf_path.name):

            if self._is_cached_pdf(candidate):

                return str(candidate)

        pdf_url = self._find_pdf_url(source.identifier)

        content = self._download_public(pdf_url)

        if not content.startswith(b"%PDF"):

            raise ValueError(
                f"DOI {source.identifier} did not return a PDF"
            )

        if not self._is_complete_pdf(content):

            raise ValueError(
                f"DOI {source.identifier} returned an incomplete PDF (the download was cut off); try again"
            )

        return str(self._store(pdf_path, content))

    # Publisher links usually redirect (to a CDN, to a login-less copy). The download is the pinned one of pdf_url_resolver: every hop is vetted (https, public addresses only) and
    # fetched from the very addresses that were vetted, so a second DNS lookup can never lead somewhere else; the body is streamed under a size limit and one deadline.
    MAX_REDIRECTS = 5

    def _download_public(self, url: str) -> bytes:
        from .pdf_url_resolver import PdfUrlError, PdfUrlResolver

        resolver = PdfUrlResolver(getaddrinfo=lambda *args, **kwargs: socket.getaddrinfo(*args, **kwargs), fetch=lambda *args: self._fetch(*args))
        delays = iter(self.RETRY_DELAYS)
        while True:
            try:
                return resolver._download(url)
            except PdfUrlError as error:  # a dropped connection or a busy server is retried like the other DOI requests; anything else surfaces at once
                delay = next(delays, None) if error.transient else None
                if delay is not None:
                    time.sleep(delay)
                    continue
                if error.kind in ("blocked", "invalid_url"):
                    raise ValueError(
                        "The PDF link listed for this DOI does not point to a public https address; "
                        "download the paper and give its .pdf path instead"
                    ) from error
                raise ValueError(f"The PDF for this DOI could not be downloaded: {error}") from error

    @staticmethod
    def _fetch(scheme, address, port, host, target, timeout):
        from .pdf_url_resolver import pinned_fetch

        return pinned_fetch(scheme, address, port, host, target, timeout)

    def _find_pdf_url(self, doi: str) -> str:

        def fetch():

            reply = requests.get(
                self.CROSSREF_API + doi,
                timeout=30,
            )

            reply.raise_for_status()

            return reply

        response = self._with_retries(fetch)

        links = response.json().get("message", {}).get("link", [])

        for link in links:

            url = link.get("URL", "")

            if link.get("content-type") == "application/pdf" and url.startswith("https://"):

                return url

        raise ValueError(
            f"No open PDF is listed for DOI {doi}; download the paper and give its .pdf path instead"
        )
