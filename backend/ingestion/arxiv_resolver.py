import os
import threading
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

        content = response.content

        # Only a whole PDF is cached, and atomically: a non-PDF reply (e.g. an
        # HTML error page) or an interrupted write must never leave a file that
        # every later attempt would reuse and fail on.
        if not content.startswith(b"%PDF"):

            raise ValueError(
                f"arXiv returned no PDF for {source.identifier}"
            )

        partial_path = pdf_path.with_name(
            f"{pdf_path.name}.{os.getpid()}.{threading.get_ident()}.part"
        )

        try:

            partial_path.write_bytes(content)

            os.replace(partial_path, pdf_path)

        finally:

            partial_path.unlink(missing_ok=True)

        return str(pdf_path)
