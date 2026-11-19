"""The content-hash analysis cache: identical files are analysed once, any change is a miss, learners stay isolated, concurrent uploads are safe, and the benchmark runs."""
import shutil
import threading
from copy import deepcopy

import pymupdf
import pytest

from backend import analysis_cache as cache_module
from backend.analysis_cache import analysis_cache, file_key
from backend.platform import platform
from backend.prereqai_eval import performance
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.delenv("PREREQAI_ANALYSIS_CACHE_DIR", raising=False)
    analysis_cache.clear()
    session_manager.sessions.clear()
    yield
    analysis_cache.clear()
    session_manager.sessions.clear()


@pytest.fixture
def runs(monkeypatch):
    """Counts the real pipeline runs."""
    calls, original = [], platform.analysis.run
    monkeypatch.setattr(platform.analysis, "run", lambda *a, **k: calls.append(1) or original(*a, **k))
    return calls


def copy_of(tmp_path, name):
    target = tmp_path / name
    shutil.copy(SAMPLE, target)
    return str(target)


def test_the_same_file_uploaded_again_does_not_rerun_the_pipeline(tmp_path, runs):
    first = platform.analyze(copy_of(tmp_path, "a.pdf"))
    second = platform.analyze(copy_of(tmp_path, "b.pdf"))  # another path, the same bytes
    assert len(runs) == 1 and (analysis_cache.hits, analysis_cache.misses) == (1, 1)
    assert first["session_id"] != second["session_id"] and first["report"]["concepts"] == second["report"]["concepts"]
    assert session_manager.get(second["session_id"]).paper.source_path.endswith("b.pdf")  # the copy belongs to the second upload


def test_changed_content_a_new_pipeline_version_and_other_ocr_settings_are_misses(tmp_path, runs, monkeypatch):
    path = copy_of(tmp_path, "a.pdf")
    key = file_key(path)
    other = tmp_path / "other.pdf"
    document = pymupdf.open(path)
    document.set_metadata({"title": "A different file"})
    document.save(str(other))
    assert file_key(str(other)) != key
    with monkeypatch.context() as scoped:
        scoped.setattr(cache_module, "PIPELINE_VERSION", "next-version")
        assert file_key(path) != key
    with monkeypatch.context() as scoped:
        scoped.setenv("PREREQAI_OCR_LANGS", "deu")
        assert file_key(path) != key
    platform.analyze(path)
    platform.analyze(str(other))
    assert len(runs) == 2


def test_learner_specific_state_never_enters_or_leaves_the_cache(tmp_path, runs):
    path = copy_of(tmp_path, "a.pdf")
    mine = platform.analyze(path, known=["Linear Algebra"], studied=["Probability"], hours_per_day=1)
    theirs = platform.analyze(path)  # served from the cache: nothing of the first learner's settings
    assert len(runs) == 1
    plan = lambda outcome: [step["concept"] for step in outcome["report"]["learning_plan"]]
    assert "Linear Algebra" not in plan(mine) and "Linear Algebra" in plan(theirs)
    assert theirs["report"]["study_time"]["daily_hours"] == 3 and mine["report"]["study_time"]["daily_hours"] == 1
    assert not any(item["completed"] for item in theirs["report"]["study_progress"])
    platform.mark_concept_studied(theirs["session_id"], "Calculus")  # a change in one session...
    third = platform.analyze(path)
    assert not any(item["completed"] for item in third["report"]["study_progress"])  # ...is not in the next analysis
    theirs["report"]["concepts"].clear()  # nor is a caller changing the report it was given
    assert platform.analyze(path)["report"]["concepts"]


def test_concurrent_uploads_of_one_file_are_analysed_once_and_each_gets_its_own_session(tmp_path, runs):
    paths = [copy_of(tmp_path, f"{i}.pdf") for i in range(6)]
    outcomes, errors = [], []

    def work(path):
        try:
            outcomes.append(platform.analyze(path))
        except Exception as error:  # pragma: no cover - reported below
            errors.append(error)

    threads = [threading.Thread(target=work, args=(p,)) for p in paths]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(runs) == 1 and all(o["status"] == "success" for o in outcomes)
    assert len({o["session_id"] for o in outcomes}) == 6
    papers = [session_manager.get(o["session_id"]).paper for o in outcomes]
    assert len({id(p) for p in papers}) == 6 and len({id(p.concepts) for p in papers}) == 6  # six independent copies


def test_a_failed_first_analysis_is_not_cached_and_the_next_one_runs(tmp_path, monkeypatch):
    path = copy_of(tmp_path, "a.pdf")
    original = platform.analysis.run
    state = {"fail": True, "calls": 0}

    def flaky(*args, **kwargs):
        state["calls"] += 1
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(platform.analysis, "run", flaky)
    assert platform.analyze(path)["status"] == "failure"
    assert platform.analyze(path)["status"] == "success" and state["calls"] == 2


def test_a_partial_ocr_result_is_never_cached(tmp_path, monkeypatch):
    original, calls = platform.analysis.run, []

    def partial(*args, **kwargs):
        calls.append(1)
        result = original(*args, **kwargs)
        result.paper.pages[0].ocr_stopped = True
        return result

    monkeypatch.setattr(platform.analysis, "run", partial)
    path = copy_of(tmp_path, "a.pdf")
    platform.analyze(path)
    platform.analyze(path)
    assert len(calls) == 2


def test_the_disk_cache_serves_a_restart_and_survives_damage(tmp_path, runs, monkeypatch):
    directory = tmp_path / "cache"
    monkeypatch.setenv("PREREQAI_ANALYSIS_CACHE_DIR", str(directory))
    path = copy_of(tmp_path, "a.pdf")
    first = platform.analyze(path)
    [entry] = list(directory.glob("*.json"))
    assert not list(directory.glob(".*tmp")) and len(runs) == 1
    analysis_cache.clear()  # a restart: only the file remains
    second = platform.analyze(path)
    assert len(runs) == 1 and second["report"]["concepts"] == first["report"]["concepts"] and analysis_cache.hits == 1
    analysis_cache.clear()
    entry.write_text("{ not json", encoding="utf-8")
    platform.analyze(path)  # the damaged entry is a miss, replaced by a good one
    assert len(runs) == 2 and entry.exists() and entry.read_text().startswith('{"paper"')


def test_the_memory_cache_is_bounded(tmp_path):
    small = cache_module.AnalysisCache(max_entries=2)
    for key in ("a", "b", "c"):
        small.fetch(key, lambda key=key: {"paper": key, "report": {}, "timings": {}})
    assert [small.fetch(key, lambda: {"paper": "new", "report": {}, "timings": {}})[1] for key in ("b", "c")] == [True, True]
    assert small.fetch("a", lambda: {"paper": "new", "report": {}, "timings": {}})[1] is False  # the oldest was dropped


def test_the_benchmark_pdf_has_the_requested_pages_and_the_benchmark_reports_every_stage(tmp_path):
    target = tmp_path / "b.pdf"
    performance.generate_pdf(target, 100)
    assert len(pymupdf.open(str(target))) == 100 
    performance.generate_pdf(tmp_path / "c.pdf", 100)
    text = lambda p: [page.get_text() for page in pymupdf.open(str(p))]
    assert text(target) == text(tmp_path / "c.pdf")  # the same text every time (the file's own creation date aside)
    report = performance.run_benchmark(100)
    assert report["pages"] == 100 and {"ingestion", "concept_detector", "report_generator"} <= set(report["cold"]["stages"])
    assert report["cold"]["peak_python_mib"] > 0 and report["peak_rss_mib"] > 0 and "cold run" in performance.render_performance(report)
    assert report["cached"]["total_seconds"] < report["cold"]["total_seconds"]  # the repeat is served by the cache (a loose ordering, not a timing budget)
