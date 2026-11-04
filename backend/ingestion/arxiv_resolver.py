import contextvars
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


# Set by the analysis pipeline for the duration of a run: a callable that raises when the run was cancelled or ran out of time.
# The download retry loop calls it before each retry, so a time limit (--max-seconds) is not outlasted by the retry delays
# and repeated 60-second attempts of a download that is failing.
RETRY_CHECKPOINT = contextvars.ContextVar("prereqai_retry_checkpoint", default=None)


class ArxivResolver(BaseSourceResolver):
    """
    Downloads arXiv papers as local PDFs.

    Downloaded files are cached to avoid
    repeated network requests.
    """

    CACHE_DIRECTORY = Path("cache/arxiv")

    @property
    def cache_directory(self) -> Path:
        """Where this resolver's downloads are cached. By default `cache/<kind>` under the current directory, so the same
        paper is downloaded again from another directory; PREREQAI_CACHE_DIR (a leading ~ is expanded, blank means unset)
        moves every cache under one fixed directory. A CACHE_DIRECTORY set to anything but the default (tests, subclasses)
        is used as given."""

        configured = os.environ.get("PREREQAI_CACHE_DIR", "").strip()

        if configured and self.CACHE_DIRECTORY.parent == Path("cache"):

            return Path(os.path.expanduser(configured)) / self.CACHE_DIRECTORY.name

        return self.CACHE_DIRECTORY

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
            self.cache_directory /
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

        if not self._is_complete_pdf(content):

            raise ValueError(
                f"arXiv returned an incomplete PDF for {source.identifier} (the download was cut off); try again"
            )

        return str(self._store(pdf_path, content))

    @staticmethod
    def _is_complete_pdf(content: bytes) -> bool:
        """A whole PDF ends with %%EOF (trailing padding is fine); a download cut off mid-transfer does not."""

        return b"%%EOF" in content[-1024:]

    @staticmethod
    def _is_cached_pdf(pdf_path: Path) -> bool:
        """A cached file is reused only if it still starts like a PDF. One left by an older version or an interrupted
        write (empty, an HTML error page) would otherwise fail every later attempt: it is dropped so the paper is
        downloaded again."""

        try:

            with open(pdf_path, "rb") as handle:

                if handle.read(4) == b"%PDF":

                    # A complete PDF ends with %%EOF; an interrupted copy that still starts with %PDF does not.
                    handle.seek(0, 2)
                    handle.seek(max(handle.tell() - 1024, 0))

                    if b"%%EOF" in handle.read():

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

    # A download is written to a `.part` file that is removed on success and on any error. A process killed mid-write (SIGKILL,
    # power loss) never reaches that cleanup, and nothing else reads the file, so its leftovers would pile up in the cache
    # forever. One older than this cannot belong to a live download and is removed the next time anything is stored.
    STALE_PARTIAL_SECONDS = 3600

    @staticmethod
    def _remove_stale_partials(directory: Path) -> None:

        cutoff = time.time() - ArxivResolver.STALE_PARTIAL_SECONDS

        try:

            for partial in directory.glob("*.part"):

                try:

                    if partial.stat().st_mtime < cutoff:

                        partial.unlink(missing_ok=True)

                except OSError:

                    pass

        except OSError:

            pass

    @staticmethod
    def _write_atomically(pdf_path: Path, content: bytes) -> Path:

        pdf_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        ArxivResolver._remove_stale_partials(pdf_path.parent)

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

        def fetch():

            response = requests.get(
                url,
                timeout=60,
            )

            response.raise_for_status()

            return response.content

        return self._with_retries(fetch)

    def _with_retries(self, fetch):
        """Run `fetch`, retrying after RETRY_DELAYS when it fails with a transient request error; the last (or a
        non-transient) failure surfaces unchanged. Shared by the arXiv and DOI downloads."""

        delays = iter(self.RETRY_DELAYS)

        while True:

            try:

                return fetch()

            except requests.exceptions.RequestException as exc:

                delay = next(delays, None)

                if delay is None or not self._is_transient(exc):

                    raise

            self._checkpoint()

            time.sleep(delay)

            self._checkpoint()

    @staticmethod
    def _checkpoint() -> None:

        check = RETRY_CHECKPOINT.get()

        if check is not None:

            check()

    def _is_transient(self, exc) -> bool:

        # a dropped connection or a body cut short mid-download is retried; a read timeout is not (it already cost
        # the full 60 seconds and is reported as a timeout at once)
        if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError)):

            return True

        return (
            isinstance(exc, requests.exceptions.HTTPError)
            and exc.response is not None
            and exc.response.status_code in self.RETRYABLE_STATUSES
        )
