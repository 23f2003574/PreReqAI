from pathlib import Path

import requests

from .research_source_detector import (
    ResearchSource,
)

from .base_source_resolver import (
    BaseSourceResolver,
)


class ArxivResolver(BaseSourceResolver):
    """
    Downloads arXiv papers as local PDFs.

    Downloaded files are cached to avoid
    repeated network requests.
    """

    CACHE_DIRECTORY = Path("cache/arxiv")

    def __init__(self):

        self.CACHE_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

    def resolve(
        self,
        source: ResearchSource,
    ) -> str:

        pdf_path = (
            self.CACHE_DIRECTORY /
            f"{source.identifier}.pdf"
        )

        if pdf_path.exists():

            return str(pdf_path)

        download_url = (
            f"https://arxiv.org/pdf/{source.identifier}.pdf"
        )

        response = requests.get(
            download_url,
            timeout=60,
        )

        response.raise_for_status()

        pdf_path.write_bytes(
            response.content
        )

        return str(pdf_path)
