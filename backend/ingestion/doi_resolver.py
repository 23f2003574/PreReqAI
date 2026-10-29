import ipaddress
import re
import socket
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
            self.CACHE_DIRECTORY /
            f"{source.identifier.replace('/', '_')}.pdf"
        )

        if self._is_cached_pdf(pdf_path):

            return str(pdf_path)

        pdf_url = self._find_pdf_url(source.identifier)

        content = self._download_public(pdf_url)

        if not content.startswith(b"%PDF"):

            raise ValueError(
                f"DOI {source.identifier} did not return a PDF"
            )

        self._store(pdf_path, content)

        return str(pdf_path)

    # Publisher links usually redirect (to a CDN, to a login-less copy); each hop is checked, not only the first.
    MAX_REDIRECTS = 5

    def _download_public(self, url: str) -> bytes:

        for _ in range(self.MAX_REDIRECTS + 1):

            if not is_public_https_url(url):

                raise ValueError(
                    "The PDF link listed for this DOI does not point to a public https address; "
                    "download the paper and give its .pdf path instead"
                )

            response = requests.get(url, timeout=60, allow_redirects=False)

            if response.is_redirect:

                url = urljoin(url, response.headers.get("Location", ""))

                continue

            response.raise_for_status()

            return response.content

        raise ValueError("Too many redirects while downloading the PDF for this DOI")

    def _find_pdf_url(self, doi: str) -> str:

        response = requests.get(
            self.CROSSREF_API + doi,
            timeout=30,
        )

        response.raise_for_status()

        links = response.json().get("message", {}).get("link", [])

        for link in links:

            url = link.get("URL", "")

            if link.get("content-type") == "application/pdf" and url.startswith("https://"):

                return url

        raise ValueError(
            f"No open PDF is listed for DOI {doi}; download the paper and give its .pdf path instead"
        )
