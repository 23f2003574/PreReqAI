"""The isolated PDF worker: a stalled, memory-hungry, crashing or oversized parse is stopped and reported, and the server is never the process that suffers it."""
import sys
import time

import pytest

from backend.ingestion import pdf_guard
from backend.ingestion.pdf_guard import PdfGuardError, guard_pdf

pytestmark = pytest.mark.prereqai


def worker(code):
    return [sys.executable, "-c", code]


def test_a_worker_that_never_finishes_is_killed_and_reported_as_a_timeout():
    started = time.monotonic()
    with pytest.raises(PdfGuardError) as error:
        guard_pdf("x.pdf", seconds=0.5, command=worker("import time; time.sleep(60)"))
    assert error.value.kind == "timeout" and "longer than 0.5 seconds" in error.value.message and time.monotonic() - started < 10


def test_the_worker_and_its_children_are_killed_so_nothing_is_left_running(tmp_path):
    marker = tmp_path / "child-alive"
    code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time,pathlib; time.sleep(2); pathlib.Path({str(marker)!r}).write_text(\"x\")']); time.sleep(60)"
    with pytest.raises(PdfGuardError):
        guard_pdf("x.pdf", seconds=0.5, command=worker(code))
    time.sleep(3)
    if sys.platform != "win32":
        assert not marker.exists()  # the grandchild was killed with the worker


def test_memory_exhaustion_a_crash_and_too_many_pages_have_their_own_kinds():
    with pytest.raises(PdfGuardError) as memory:
        guard_pdf("x.pdf", memory_mb=64, command=worker("import sys; print('{\"error\": \"memory\"}'); sys.exit(3)"))
    assert memory.value.kind == "resource_exhausted" and "64 MB" in memory.value.message
    with pytest.raises(PdfGuardError) as crash:
        guard_pdf("x.pdf", command=worker("import os, signal; os.kill(os.getpid(), signal.SIGSEGV)" if sys.platform != "win32" else "import sys; sys.exit(9)"))
    assert crash.value.kind == "worker_failed" and "stopped unexpectedly" in crash.value.message
    with pytest.raises(PdfGuardError) as pages:
        guard_pdf("x.pdf", max_pages=10, command=worker("print('{\"pages\": 5000, \"too_many_pages\": true}')"))
    assert pages.value.kind == "too_many_pages" and "5000 pages; the limit is 10" in pages.value.message


def test_a_handled_file_and_an_unreadable_one_pass_through_to_the_normal_analysis():
    assert guard_pdf("x.pdf", command=worker("print('{\"pages\": 3, \"readable\": true, \"memory_limit_applied\": true}')"))["pages"] == 3
    unreadable = guard_pdf("x.pdf", command=worker("import sys; print('{\"error\": \"unreadable\"}'); sys.exit(4)"))
    assert unreadable["readable"] is False  # the analysis words an unreadable file as it always has


def test_limits_come_from_the_environment_and_fall_back_when_malformed(monkeypatch):
    assert pdf_guard.limits() == (1000, 120.0, 2048)
    monkeypatch.setenv("PREREQAI_MAX_PDF_PAGES", "50")
    monkeypatch.setenv("PREREQAI_PARSE_SECONDS", "7.5")
    monkeypatch.setenv("PREREQAI_PARSE_MEMORY_MB", "0")
    assert pdf_guard.limits() == (50, 7.5, 0)
    monkeypatch.setenv("PREREQAI_MAX_PDF_PAGES", "lots")
    monkeypatch.setenv("PREREQAI_PARSE_SECONDS", "-3")
    assert pdf_guard.limits()[:2] == (1000, 120.0)


def test_a_missing_worker_binary_is_a_worker_failure_not_a_crash():
    with pytest.raises(PdfGuardError) as error:
        guard_pdf("x.pdf", command=["/nonexistent/python"])
    assert error.value.kind == "worker_failed" and "could not be started" in error.value.message


def test_testserver_is_not_a_production_host(monkeypatch):
    from backend import security

    monkeypatch.delenv(security.TEST_ENV, raising=False)
    assert not security.host_allowed("testserver") and security.host_allowed("localhost:8000")
    monkeypatch.setenv(security.TEST_ENV, "1")
    assert security.host_allowed("testserver")
