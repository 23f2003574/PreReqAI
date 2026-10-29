import os
import tempfile
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

        # The cache directory is created when a download is stored, not here: building the resolver (which every
        # analysis does, even of a local PDF) must not write into, or fail because of, the current directory.
        pass

    def resolve(
        self,
        source: ResearchSource,
    ) -> str:

        pdf_path = (
            self.CACHE_DIRECTORY /
            f"{source.identifier.replace('/', '_')}.pdf"  # an old-style id ("hep-th/9901001") has a slash
        )

        for candidate in (pdf_path, self._fallback_directory() / pdf_path.name):

            if self._is_cached_pdf(candidate):

                return str(candidate)

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

        return str(self._store(pdf_path, content))

    @staticmethod
    def _is_cached_pdf(pdf_path: Path) -> bool:
        """A cached file is reused only if it still starts like a PDF. One left by an older version or an interrupted
        write (empty, an HTML error page) would otherwise fail every later attempt: it is dropped so the paper is
        downloaded again."""

        try:

            with open(pdf_path, "rb") as handle:

                if handle.read(4) == b"%PDF":

                    return True

        except OSError:

            return False

        pdf_path.unlink(missing_ok=True)

        return False

    def _fallback_directory(self) -> Path:
        """Where downloads go when the working directory cannot be written (a read-only or unusual current directory)."""

        return Path(tempfile.gettempdir()) / "prereqai-cache" / self.CACHE_DIRECTORY.name

    def _store(self, pdf_path: Path, content: bytes) -> Path:
        """Cache the download beside the working directory; if that cannot be written, in the temp directory instead:
        a paper that was downloaded must not fail the analysis because it could not be cached. Returns the file used."""

        try:

            return self._write_atomically(pdf_path, content)

        except OSError:

            return self._write_atomically(self._fallback_directory() / pdf_path.name, content)

    @staticmethod
    def _write_atomically(pdf_path: Path, content: bytes) -> Path:

        pdf_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        partial_path = pdf_path.with_name(
            f"{pdf_path.name}.{os.getpid()}.{threading.get_ident()}.part"
        )

        try:

            partial_path.write_bytes(content)

            os.replace(partial_path, pdf_path)

        finally:

            partial_path.unlink(missing_ok=True)

        return pdf_path

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
