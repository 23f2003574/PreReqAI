import os
import threading
import time
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

    # A download is a plain GET, so repeating it is safe. A refused/dropped
    # connection or a busy arXiv (429/5xx) is usually gone a moment later;
    # anything else (a 404, a non-PDF reply, a read timeout) is not retried.
    RETRY_DELAYS = (1.0, 3.0)

    RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

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

        content = self._download(download_url)

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

    def _download(self, url: str) -> bytes:

        delays = iter(self.RETRY_DELAYS)

        while True:

            try:

                response = requests.get(
                    url,
                    timeout=60,
                )

                response.raise_for_status()

                return response.content

            except requests.exceptions.RequestException as exc:

                delay = next(delays, None)

                if delay is None or not self._is_transient(exc):

                    raise  # the last (or a non-transient) failure surfaces unchanged

            time.sleep(delay)

    def _is_transient(self, exc) -> bool:

        if isinstance(exc, requests.exceptions.ConnectionError):

            return True

        return (
            isinstance(exc, requests.exceptions.HTTPError)
            and exc.response is not None
            and exc.response.status_code in self.RETRYABLE_STATUSES
        )
