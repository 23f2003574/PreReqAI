"""The analysis limit is shared by every worker process: two processes cannot both take the last slot, and a process that dies frees its slot."""
import multiprocessing
import os
import signal
import time

import pytest

from backend import analysis_slots

pytestmark = pytest.mark.prereqai
pytest.importorskip("fcntl")


def _hold(directory, limit, ready, stop):
    os.environ["PREREQAI_SLOTS_DIR"], os.environ[analysis_slots.SLOTS_ENV] = directory, str(limit)
    ready.put(analysis_slots.try_acquire())
    stop.wait(30)


def _try(directory, limit, results):
    os.environ["PREREQAI_SLOTS_DIR"], os.environ[analysis_slots.SLOTS_ENV] = directory, str(limit)
    results.put(analysis_slots.try_acquire())


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv(analysis_slots.SLOTS_ENV, "1")
    monkeypatch.setenv(analysis_slots.DIR_ENV, str(tmp_path / "slots"))
    context = multiprocessing.get_context("spawn")
    yield str(tmp_path / "slots"), context
    while analysis_slots._held:
        analysis_slots.release()


def test_two_processes_cannot_both_take_the_last_slot(setup):
    directory, context = setup
    ready, stop = context.Queue(), context.Event()
    holder = context.Process(target=_hold, args=(directory, 1, ready, stop))
    holder.start()
    assert ready.get(timeout=30) is True
    assert analysis_slots.try_acquire() is False and analysis_slots.active() == 1  # this process sees the other's slot
    stop.set()
    holder.join(30)
    assert analysis_slots.try_acquire() is True and analysis_slots.active() == 1


def test_simultaneous_processes_get_exactly_the_limit(setup):
    directory, context = setup
    results = context.Queue()
    stop = context.Event()
    processes = [context.Process(target=_hold, args=(directory, 2, results, stop)) for _ in range(3)]
    for process in processes:
        process.start()
    outcomes = [results.get(timeout=120) for _ in processes]
    assert sum(outcomes) == 2
    stop.set()
    for process in processes:
        process.terminate()
        process.join(10)


def test_a_process_killed_while_holding_a_slot_does_not_exhaust_capacity(setup):
    directory, context = setup
    ready, stop = context.Queue(), context.Event()
    holder = context.Process(target=_hold, args=(directory, 1, ready, stop))
    holder.start()
    assert ready.get(timeout=30) is True
    assert analysis_slots.try_acquire() is False
    os.kill(holder.pid, signal.SIGKILL)
    holder.join(30)
    deadline = time.time() + 10
    while not analysis_slots.try_acquire() and time.time() < deadline:
        time.sleep(0.1)
    assert analysis_slots.active() == 1


def test_release_frees_a_slot_and_an_extra_release_is_harmless(setup):
    assert analysis_slots.try_acquire() and analysis_slots.active() == 1
    analysis_slots.release()
    analysis_slots.release()
    assert analysis_slots.active() == 0 and analysis_slots.try_acquire()
