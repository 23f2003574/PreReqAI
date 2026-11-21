"""A subprocess boundary in front of the in-process analysis of an uploaded PDF.

A hostile or pathological PDF can hang the parser or exhaust memory, and in-process that stalls or kills the whole local server. `guard_pdf` first has a short-lived worker process
(`python -m backend.ingestion.pdf_guard PATH`) open the file and extract the text of every page under limits; only a file the worker handled is analysed in the server.
* page limit: PREREQAI_MAX_PDF_PAGES (default 1000), checked before any page is read;
* time limit: PREREQAI_PARSE_SECONDS (default 120). A worker that exceeds it, with all its children, is killed and reaped;
* memory limit: PREREQAI_PARSE_MEMORY_MB (default 2048, 0 turns it off), applied in the worker with RLIMIT_AS where the operating system has it (Linux, macOS). Where it does not (Windows)
  the page and time limits still hold and `memory_limit_applied` is False in the result.
A file the worker cannot open is not a guard failure: the analysis reports it as before, with its own message. Failures raise PdfGuardError whose `kind` is one of
"too_many_pages", "timeout", "resource_exhausted" or "worker_failed", and the upload route turns each into the matching structured response."""
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULTS = {"PREREQAI_MAX_PDF_PAGES": 1000, "PREREQAI_PARSE_SECONDS": 120.0, "PREREQAI_PARSE_MEMORY_MB": 2048}
ROOT = Path(__file__).resolve().parents[2]
EXIT_MEMORY = 3


class PdfGuardError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind, self.message = kind, message


def _setting(name, cast):
    try:
        value = cast(os.environ.get(name, "").strip())
        return value if value >= 0 else DEFAULTS[name]
    except ValueError:
        return DEFAULTS[name]


def limits():
    """(max_pages, seconds, memory_mb) from the environment; a blank, malformed or negative value is the default."""
    pages, seconds = _setting("PREREQAI_MAX_PDF_PAGES", int) or DEFAULTS["PREREQAI_MAX_PDF_PAGES"], _setting("PREREQAI_PARSE_SECONDS", float) or DEFAULTS["PREREQAI_PARSE_SECONDS"]
    return pages, seconds, _setting("PREREQAI_PARSE_MEMORY_MB", int)


def _kill(process):
    try:
        if os.name == "posix":
            import signal

            os.killpg(process.pid, signal.SIGKILL)  # the worker leads its own process group: its children go with it
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        process.kill()
    process.communicate()  # reap it, so no zombie is left


def guard_pdf(path, max_pages=None, seconds=None, memory_mb=None, command=None):
    """The worker's result {"pages": n, "readable": bool, "memory_limit_applied": bool} for a file it handled; PdfGuardError for a limit or a worker failure.
    `command` replaces the worker's argument list (for tests)."""
    default_pages, default_seconds, default_memory = limits()
    max_pages, seconds = max_pages or default_pages, seconds or default_seconds
    memory_mb = default_memory if memory_mb is None else memory_mb
    command = command or [sys.executable, "-m", "backend.ingestion.pdf_guard", str(path), str(max_pages), str(memory_mb)]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT), text=True, start_new_session=(os.name == "posix"))
    except OSError as error:
        raise PdfGuardError("worker_failed", f"the PDF worker could not be started ({error})") from None
    try:
        out, err = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        _kill(process)
        raise PdfGuardError("timeout", f"reading this PDF took longer than {seconds:g} seconds and was stopped") from None
    try:
        result = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except ValueError:
        result = {}
    if process.returncode == 0 and "pages" in result:
        if result.get("too_many_pages"):
            raise PdfGuardError("too_many_pages", f"this PDF has {result['pages']} pages; the limit is {max_pages}")
        return result
    if process.returncode == EXIT_MEMORY or result.get("error") == "memory":
        raise PdfGuardError("resource_exhausted", f"reading this PDF needed more than {memory_mb} MB of memory and was stopped")
    if result.get("error") == "unreadable":
        return {"pages": 0, "readable": False, "memory_limit_applied": bool(result.get("memory_limit_applied"))}  # the analysis reports an unreadable file as it always has
    detail = f"exit status {process.returncode}" if process.returncode >= 0 else f"killed by signal {-process.returncode}"
    raise PdfGuardError("worker_failed", f"the PDF worker stopped unexpectedly ({detail}); the file may be damaged or hostile")


def _apply_memory_limit(memory_mb):
    if not memory_mb:
        return False
    try:
        import resource

        limit = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        return True
    except (ImportError, ValueError, OSError):
        return False


def _worker(path, max_pages, memory_mb):
    applied = _apply_memory_limit(memory_mb)
    try:
        import pymupdf

        pymupdf.TOOLS.mupdf_display_errors(False)
        with pymupdf.open(path) as pdf:
            pages = pdf.page_count
            if pages > max_pages:
                print(json.dumps({"pages": pages, "too_many_pages": True, "memory_limit_applied": applied}))
                return 0
            for page in pdf:
                page.get_text("text")
        print(json.dumps({"pages": pages, "readable": True, "memory_limit_applied": applied}))
        return 0
    except MemoryError:
        print(json.dumps({"error": "memory"}))
        return EXIT_MEMORY
    except Exception as error:  # not a PDF, encrypted, damaged: the analysis words this itself
        print(json.dumps({"error": "unreadable", "detail": type(error).__name__, "memory_limit_applied": applied}))
        return 4


if __name__ == "__main__":
    sys.exit(_worker(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
