"""/health reports the analysis slots in use, and a status probe never makes an analysis lose its slot."""
import multiprocessing
import time

import pytest
from fastapi.testclient import TestClient

from backend import analysis_slots
from backend.main import app

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def two_slots(monkeypatch):
    monkeypatch.setenv(analysis_slots.SLOTS_ENV, "2")
    yield
    while analysis_slots._held:
        analysis_slots.release()


def test_health_reports_the_limit_and_the_slots_in_use():
    assert client.get("/health").json()["analysis"] == {"limit": 2, "active": 0}
    assert analysis_slots.try_acquire()
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["analysis"] == {"limit": 2, "active": 1}


def test_health_still_answers_when_the_slot_folder_is_unusable(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv(analysis_slots.DIR_ENV, str(blocker / "slots"))
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["analysis"] == {"limit": 2, "active": None}


def _probe(directory, stop):
    import os

    os.environ["PREREQAI_SLOTS_DIR"], os.environ[analysis_slots.SLOTS_ENV] = directory, "1"
    while not stop.is_set():
        analysis_slots.active()


def test_another_process_probing_the_slots_never_makes_a_free_slot_refuse(monkeypatch, tmp_path):
    monkeypatch.setenv(analysis_slots.SLOTS_ENV, "1")
    monkeypatch.setenv(analysis_slots.DIR_ENV, str(tmp_path / "slots"))
    context = multiprocessing.get_context("spawn")
    stop = context.Event()
    prober = context.Process(target=_probe, args=(str(tmp_path / "slots"), stop))
    prober.start()
    try:
        time.sleep(1.0)  # the prober is importing and looping now
        refused = 0
        for _ in range(2000):
            refused += not analysis_slots.try_acquire()
            analysis_slots.release()
    finally:
        stop.set()
        prober.join(30)
    assert refused == 0
