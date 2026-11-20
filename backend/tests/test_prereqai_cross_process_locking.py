"""Cross-process file locking: four processes recording 100 answers keep all 100, and sessions, the analysis cache and the lock itself behave under concurrent writers."""
import json
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path

import pytest

from backend import learner_profile
from backend.filelock import LockTimeout, lock_path, locked
from backend.tests import lock_support as support

pytestmark = pytest.mark.prereqai
CONTEXT = mp.get_context("spawn")  # a clean interpreter per worker, as separate server workers are


def run(target, *argument_sets):
    processes = [CONTEXT.Process(target=target, args=arguments) for arguments in argument_sets]
    [p.start() for p in processes]
    [p.join(120) for p in processes]
    assert all(p.exitcode == 0 for p in processes), [p.exitcode for p in processes]


def test_four_processes_recording_one_hundred_answers_keep_all_of_them(tmp_path):
    path = str(tmp_path / "p.json")
    run(support.record_answers, *[(path, worker, 25) for worker in range(1, 5)])
    profile, problem = learner_profile.load_full(path)
    assert problem == "" and len(profile["quiz"]) == 100  # was 62 of 100 with only a thread lock
    assert not list(tmp_path.glob(".*tmp"))


def test_concurrent_profile_updates_from_several_processes_all_land(tmp_path):
    path = str(tmp_path / "p.json")
    groups = [["Linear Algebra", "Probability"], ["Calculus", "Statistics"], ["Optimization", "Graphs"], ["Neural Networks", "Information Theory"]]
    run(support.update_known, *[(path, group) for group in groups])
    assert set(learner_profile.load_full(path)[0]["known"]) == {name for group in groups for name in group}


def test_concurrent_session_saves_from_several_processes_leave_valid_files(tmp_path):
    run(support.save_sessions, *[(str(tmp_path), worker, 5) for worker in range(4)])
    files = [f for f in tmp_path.iterdir() if f.suffix == ".session"]
    assert len(files) == 20 and not list(tmp_path.glob("*.tmp"))
    for file in files:
        data = json.loads(file.read_bytes())
        assert data["format"] == "prereqai-session" and data["session"]["f"]["paper_title"].endswith("-again")  # the last save of each session is whole


def test_concurrent_cache_writers_never_leave_a_partial_entry(tmp_path):
    key = "a" * 64 + "-" + "b" * 12
    run(support.fill_cache, *[(str(tmp_path), key, 6) for _ in range(4)])
    entry = tmp_path / f"{key}.json"
    data = json.loads(entry.read_text())  # whole, valid JSON
    assert data["report"]["pad"] == "x" * 5000 and not list(tmp_path.glob(".*tmp"))


def test_a_second_process_waits_for_the_lock_and_then_gets_it(tmp_path):
    target, ready = tmp_path / "f.json", tmp_path / "ready"
    holder = CONTEXT.Process(target=support.hold, args=(str(target), 1.0, str(ready)))
    holder.start()
    while not ready.exists():
        time.sleep(0.02)
    started = time.monotonic()
    with locked(target):
        waited = time.monotonic() - started
    holder.join(30)
    assert waited >= 0.5  # it queued behind the other process


def test_waiting_too_long_raises_instead_of_blocking_for_ever(tmp_path):
    target, ready = tmp_path / "f.json", tmp_path / "ready"
    holder = CONTEXT.Process(target=support.hold, args=(str(target), 2.0, str(ready)))
    holder.start()
    while not ready.exists():
        time.sleep(0.02)
    with pytest.raises(LockTimeout):
        with locked(target, timeout=0.3):
            pass
    holder.join(30)
    with locked(target, timeout=5):  # released when the holder finished
        pass


def test_the_lock_is_released_after_an_exception_and_can_be_nested(tmp_path):
    target = tmp_path / "f.json"
    with pytest.raises(RuntimeError):
        with locked(target):
            with locked(target):  # the same thread may enter again
                raise RuntimeError("boom")
    holder_done = []
    thread = threading.Thread(target=lambda: (locked(target, timeout=2).__enter__(), holder_done.append(True)))
    thread.start()
    thread.join(5)
    assert holder_done == [True] and lock_path(target).parent.name.startswith("prereqai-locks-") and lock_path(target).parent != target.parent


def test_threads_of_one_process_still_queue(tmp_path):
    target, order = tmp_path / "f.json", []

    def work(name):
        with locked(target):
            order.append(f"{name}-in")
            time.sleep(0.05)
            order.append(f"{name}-out")

    threads = [threading.Thread(target=work, args=(n,)) for n in "abc"]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert all(order[i].endswith("-in") and order[i + 1] == order[i].replace("-in", "-out") for i in range(0, 6, 2))  # never interleaved


def test_lock_files_never_appear_in_the_data_directories(tmp_path):
    learner_profile.record_quiz(tmp_path / "me.json", "Softmax:1", "Softmax", "knew")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["me.json"] and learner_profile.profile_names(tmp_path) == ["me"]
    assert lock_path(tmp_path / "me.json") != lock_path(tmp_path / "other.json") and lock_path(tmp_path / "me.json") == lock_path(tmp_path / "." / "me.json")
