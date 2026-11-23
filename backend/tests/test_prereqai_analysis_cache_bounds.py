"""The analysis cache stays bounded on disk and in its lock table: least recently used entries are pruned, stale temporary files are removed, and a lock is dropped when its analysis ends."""
import os
import threading
import time

import pytest

from backend import analysis_cache
from backend.analysis_cache import AnalysisCache

pytestmark = pytest.mark.prereqai


def fill(directory, names, start=1_000_000):
    for offset, name in enumerate(names):
        path = directory / name
        path.write_text("{}")
        os.utime(path, (start + offset, start + offset))


def test_prune_removes_the_least_recently_used_entries_beyond_the_limit(tmp_path):
    fill(tmp_path, ["a.json", "b.json", "c.json", "d.json"])
    removed = AnalysisCache().prune_disk(tmp_path, limit=2, now=2_000_000)
    assert sorted(removed) == ["a.json", "b.json"] and sorted(p.name for p in tmp_path.iterdir()) == ["c.json", "d.json"]


def test_reading_an_entry_refreshes_it_so_it_is_pruned_last(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_ANALYSIS_CACHE_DIR", str(tmp_path))
    cache = AnalysisCache()
    for name in ("old", "mid", "new"):
        cache._write_disk(name, {"paper": None, "report": {"n": name}, "timings": {}})
    for offset, name in enumerate(("old", "mid", "new")):
        os.utime(tmp_path / f"{name}.json", (1_000_000 + offset, 1_000_000 + offset))
    assert cache._read_disk("old") is not None  # "old" is now the most recently used
    assert cache.prune_disk(limit=2, now=time.time() + 5) == ["mid.json"]


def test_stale_temporary_files_go_and_fresh_ones_stay(tmp_path):
    fill(tmp_path, [".k.1.2.tmp", ".k.3.4.tmp", "keep.json"], start=1_000_000)
    os.utime(tmp_path / ".k.3.4.tmp", (1_999_000, 1_999_000))
    removed = AnalysisCache().prune_disk(tmp_path, limit=10, now=2_000_000)
    assert removed == [".k.1.2.tmp"] and (tmp_path / ".k.3.4.tmp").exists() and (tmp_path / "keep.json").exists()


def test_writing_prunes_to_the_configured_limit_and_a_bad_limit_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_ANALYSIS_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("PREREQAI_ANALYSIS_CACHE_MAX_ENTRIES", "3")
    cache = AnalysisCache()
    for number in range(6):
        cache._write_disk(f"key{number}", {"paper": None, "report": {"n": number}, "timings": {}})
        os.utime(tmp_path / f"key{number}.json", (1_000_000 + number, 1_000_000 + number))
    assert len(list(tmp_path.glob("*.json"))) <= 4 and (tmp_path / "key5.json").exists()
    for bad in ("0", "-2", "many", "2.5", ""):
        monkeypatch.setenv("PREREQAI_ANALYSIS_CACHE_MAX_ENTRIES", bad)
        assert AnalysisCache.disk_limit() == analysis_cache.DEFAULT_DISK_ENTRIES


def test_the_lock_table_is_empty_after_the_analyses_end_even_when_one_fails():
    cache = AnalysisCache()
    for number in range(50):
        cache.fetch(f"k{number}", lambda: {"paper": {}, "report": {}, "timings": {}})
    with pytest.raises(RuntimeError):
        cache.fetch("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cache._locks == {}


def test_concurrent_callers_for_one_key_still_analyse_once_and_leave_no_lock():
    cache, calls, gate = AnalysisCache(), [], threading.Barrier(4)

    def produce():
        calls.append(1)
        time.sleep(0.05)
        return {"paper": {}, "report": {"r": 1}, "timings": {}}

    results = []

    def worker():
        gate.wait()
        results.append(cache.fetch("same", produce)[1])

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1 and sorted(results) == [False, True, True, True] and cache._locks == {}
