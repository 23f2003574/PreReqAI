"""The whole reading of an uploaded PDF in a short-lived worker process: text layer and layout, figures, tables and OCR.

`pdf_guard` only proves a file can be opened and its text read; the analysis then parsed it again inside the server (PyMuPDF layout, pdfplumber tables, OCR rendering), so a file that is harmless to
`get_text` but hostile to those still ran with the server's memory and time. Here the worker (`python -m backend.ingestion.isolated_parse PATH ...`) does all of that under limits and prints one
JSON line, the encoded RawDocument with the figures and tables, which the server decodes; the server itself never opens the file on this path (see `IsolatedStages`).
* page limit PREREQAI_MAX_PDF_PAGES and rendered-pixel limit PREREQAI_MAX_PAGE_PIXELS (default 200 million pixels of a page at the 300 dpi OCR uses): checked before any page is read;
* time limit PREREQAI_WORKER_SECONDS (default 600): the worker and its children (its own process group) are killed and reaped;
* CPU limit (RLIMIT_CPU, the time limit plus 10 s) and memory limit PREREQAI_PARSE_MEMORY_MB (RLIMIT_AS) where the operating system has them; `limits_applied` in the result says which held;
* output limit PREREQAI_MAX_WORKER_OUTPUT_MB (default 256).
Failures raise PdfGuardError (kinds too_many_pages, page_too_large, timeout, resource_exhausted, worker_failed). PREREQAI_PARSE_INPROCESS=1 (set by the test suite, never by default) reads in the server as before."""
import json
import os
import subprocess
import sys
from contextvars import ContextVar
from types import SimpleNamespace

from .pdf_guard import EXIT_MEMORY, ROOT, PdfGuardError, _kill, _setting, limits

ISOLATED = ContextVar("prereqai_isolated_parse", default=False)  # set by the upload route for the request's analysis
DEFAULT_PIXELS, DEFAULT_SECONDS, DEFAULT_OUTPUT_MB = 200_000_000, 600.0, 256
_REPAIRED = {}


def enabled():
    """Whether the analysis of the current request reads its PDF in the worker."""
    return ISOLATED.get() and os.environ.get("PREREQAI_PARSE_INPROCESS", "") != "1"


def settings():
    pages, _, memory = limits()
    pixels = _setting("PREREQAI_MAX_PAGE_PIXELS", int) or DEFAULT_PIXELS
    seconds = _setting("PREREQAI_WORKER_SECONDS", float) or DEFAULT_SECONDS
    return pages, pixels, seconds, memory, _setting("PREREQAI_MAX_WORKER_OUTPUT_MB", int) or DEFAULT_OUTPUT_MB


PDF_HEADER_WINDOW = 1024  # the PDF specification lets a file begin with up to this many bytes before "%PDF-"


def looks_like_pdf(path):
    """Whether the file starts like a PDF: "%PDF-" within its first 1024 bytes. A file that cannot be opened is left to the worker, which reports it."""
    try:
        with open(path, "rb") as handle:
            return b"%PDF-" in handle.read(PDF_HEADER_WINDOW)
    except OSError:
        return True


def run_worker(path, ocr_seconds=None, command=None, seconds=None):
    """The PDF worker run, with its lifecycle logged (see backend/observability.py): worker_start with the limits, then worker_end with the duration, or worker_failed with the guard's code
    (timeout, too_many_pages, page_too_large, resource_exhausted, worker_failed) as the reason and an error category. The file's name and path are never logged."""
    from time import perf_counter

    from backend.observability import categorise, log_event

    if not looks_like_pdf(path):  # the file's own bytes decide, not its name or content type: no worker process is started for text, HTML, an archive or an empty file
        log_event("worker_refused", level=30, reason="not_a_pdf", error_category="invalid_input")
        raise PdfGuardError("worker_failed", "this file could not be read as a PDF (it does not start with a PDF header)")
    log_event("worker_start", pages_limit=settings()[0], seconds_limit=seconds or settings()[2], memory_mb_limit=settings()[3])
    started = perf_counter()
    try:
        result = _run_worker(path, ocr_seconds, command, seconds)
    except PdfGuardError as error:
        log_event("worker_failed", level=40, reason=error.kind, error_category=categorise(error), duration_ms=(perf_counter() - started) * 1000, killed=error.kind == "timeout")
        raise
    log_event("worker_end", outcome="ok", duration_ms=(perf_counter() - started) * 1000, repaired=bool(result.get("repaired")))
    return result


def _run_worker(path, ocr_seconds=None, command=None, seconds=None):
    """The decoded {"document", "figures", "tables", "repaired", "limits_applied"} of the worker; PdfGuardError for a limit or a failure. `command` replaces the worker's arguments (tests)."""
    from backend.session import session_codec

    pages, pixels, default_seconds, memory, out_mb = settings()
    seconds = seconds or default_seconds
    command = command or [sys.executable, "-m", "backend.ingestion.isolated_parse", str(path), str(pages), str(pixels), str(memory), str(int(seconds)), str(out_mb),
                          "" if ocr_seconds is None else str(ocr_seconds)]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT), text=True, start_new_session=(os.name == "posix"))
    except OSError as error:
        raise PdfGuardError("worker_failed", f"the PDF worker could not be started ({error})") from None
    try:
        out, _ = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        _kill(process)
        raise PdfGuardError("timeout", f"reading this PDF took longer than {seconds:g} seconds and was stopped") from None
    try:
        result = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except ValueError:
        result = {}
    if process.returncode == 0 and result.get("ok"):
        return {"document": session_codec.decode(result["document"]), "figures": session_codec.decode(result["figures"]), "tables": session_codec.decode(result["tables"]),
                "repaired": bool(result.get("repaired")), "limits_applied": result.get("limits_applied", {})}
    error = result.get("error")
    if error in ("too_many_pages", "page_too_large"):
        raise PdfGuardError(error, result.get("message", "this PDF is over a limit"))
    if process.returncode == EXIT_MEMORY or error == "memory":
        raise PdfGuardError("resource_exhausted", f"reading this PDF needed more than {memory} MB of memory and was stopped")
    if error == "output_too_large":
        raise PdfGuardError("resource_exhausted", "the text and structure of this PDF are larger than the limit and it was stopped")
    if error == "password_protected":
        raise PdfGuardError("worker_failed", "this PDF is password-protected, so it cannot be read (remove the password, for example by printing it to a new PDF, and upload that)")
    if error == "unreadable":
        raise PdfGuardError("worker_failed", f"this file could not be read as a PDF ({result.get('detail', 'unreadable')})")
    detail = f"exit status {process.returncode}" if process.returncode >= 0 else f"killed by signal {-process.returncode}"
    raise PdfGuardError("worker_failed", f"the PDF worker stopped unexpectedly ({detail}); the file may be damaged or hostile")


class IsolatedStages:
    """The pipeline's ingestion, figure and table stages, answered from one worker run per file (the worker is started by the first of them)."""

    def __init__(self, ocr_seconds=None, runner=run_worker):
        self.ocr_seconds, self.runner, self.cache = ocr_seconds, runner, {}

    def _result(self, path):
        if path not in self.cache:
            self.cache[path] = self.runner(path, self.ocr_seconds)
            _REPAIRED[str(path)] = self.cache[path]["repaired"]
        return self.cache[path]

    def ingest(self, pdf_path):
        return self._result(pdf_path)["document"]

    def figures(self, pdf_path, paper):
        paper.figures = self._result(pdf_path)["figures"]
        return paper

    def tables(self, pdf_path, paper):
        paper.tables = self._result(pdf_path)["tables"]
        return paper


def was_repaired(path):
    """Whether the worker found the PDF damaged and repaired (None when it never read this path)."""
    return _REPAIRED.get(str(path))


def _apply_limits(memory_mb, cpu_seconds):
    applied = {"memory": False, "cpu": False}
    try:
        import resource

        for name, limit, key in (("RLIMIT_AS", memory_mb * 1024 * 1024 if memory_mb else 0, "memory"), ("RLIMIT_CPU", cpu_seconds, "cpu")):
            if limit:
                resource.setrlimit(getattr(resource, name), (limit, limit))
                applied[key] = True
    except (ImportError, ValueError, OSError, AttributeError):
        pass
    return applied


def _fail(error, code, **more):
    print(json.dumps({"ok": False, "error": error, **more}))
    return code


def _worker(path, max_pages, max_pixels, memory_mb, seconds, out_mb, ocr_seconds):
    applied = _apply_limits(memory_mb, int(seconds) + 10)
    try:
        import pymupdf

        pymupdf.TOOLS.mupdf_display_errors(False)
        with pymupdf.open(path) as pdf:
            if pdf.needs_pass:  # encrypted with a password it cannot know: say so instead of failing later with a bare exception name
                return _fail("password_protected", 4)
            if pdf.page_count > max_pages:
                return _fail("too_many_pages", 0, message=f"this PDF has {pdf.page_count} pages; the limit is {max_pages}")
            for number, page in enumerate(pdf, start=1):
                rect = page.rect
                pixels = (rect.width * 300 / 72) * (rect.height * 300 / 72)  # the size of the page as OCR renders it
                if pixels > max_pixels:
                    return _fail("page_too_large", 0, message=f"page {number} is {rect.width:.0f} x {rect.height:.0f} points; rendering it would need {pixels / 1e6:.0f} million pixels (the limit is {max_pixels / 1e6:.0f})")
    except MemoryError:
        return _fail("memory", EXIT_MEMORY)
    except Exception as error:
        return _fail("unreadable", 4, detail=type(error).__name__)
    try:
        from backend.ingestion import PDFIngestionEngine
        from backend.parsing import FigureExtractor, TableExtractor
        from backend.session import session_codec

        engine = PDFIngestionEngine(max_ocr_seconds=float(ocr_seconds) if ocr_seconds else None)
        document = engine.ingest(path)
        holder = SimpleNamespace(figures=[], tables=[])
        FigureExtractor().extract(path, holder)
        TableExtractor().extract(path, holder)
        with pymupdf.open(path) as pdf:
            repaired = bool(pdf.is_repaired)
        text = json.dumps({"ok": True, "document": session_codec.encode(document), "figures": session_codec.encode(holder.figures), "tables": session_codec.encode(holder.tables),
                           "repaired": repaired, "limits_applied": applied}, ensure_ascii=False, allow_nan=False)
    except MemoryError:
        return _fail("memory", EXIT_MEMORY)
    except Exception as error:
        return _fail("unreadable", 4, detail=type(error).__name__)
    if len(text) > out_mb * 1024 * 1024:
        return _fail("output_too_large", 5)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(_worker(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]), sys.argv[7]))
