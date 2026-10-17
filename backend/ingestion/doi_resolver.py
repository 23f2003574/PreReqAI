import re
from pathlib import Path

import requests

from .arxiv_resolver import ArxivResolver

from .research_source_detector import (
    ResearchSource,
)

ARXIV_DOI_PATTERN = re.compile(
    r"10\.48550/arxiv\.([0-9]+\.[0-9]+(?:v[0-9]+)?)",
    re.IGNORECASE,
)


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

        if pdf_path.exists():

            return str(pdf_path)

        pdf_url = self._find_pdf_url(source.identifier)

        content = self._download(pdf_url)

        if not content.startswith(b"%PDF"):

            raise ValueError(
                f"DOI {source.identifier} did not return a PDF"
            )

        self._store(pdf_path, content)

        return str(pdf_path)

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
