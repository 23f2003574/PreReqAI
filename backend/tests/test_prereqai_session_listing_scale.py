"""Listing and restoring many saved sessions keeps the in-memory cap instead of loading every saved file into memory."""
import copy
import uuid

import pytest

from backend.platform import platform
from backend.session import session_manager as manager

SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(type(manager), "MAX_SESSIONS_IN_MEMORY", 5)
    template = manager.get(platform.analyze(SAMPLE)["session_id"])
    ids = []
    for created in range(40):
        session = copy.deepcopy(template)
        session.session_id, session.created_at = str(uuid.uuid4()), float(created)
        manager.save(session)
        ids.append(session.session_id)
    manager.sessions.clear()
    manager._last_used.clear()
    yield ids
    manager.sessions.clear()
    manager._last_used.clear()


def test_listing_shows_every_saved_session_without_caching_them_all(saved):
    listed = manager.list()

    assert [s.session_id for s in listed if s.session_id in saved] == saved[::-1]  # newest first, none dropped
    assert len(manager.sessions) == 0


def test_restoring_saved_sessions_one_by_one_stays_within_the_cap(saved):
    for session_id in saved:
        assert manager.get(session_id).session_id == session_id

    assert len(manager.sessions) <= 5
    assert manager.get(saved[0]) is not None  # an evicted one is restored again on request


def test_summaries_match_the_listing_and_reread_only_changed_files(saved, monkeypatch):
    expected = [(s.session_id, s.paper_title, s.created_at, s.report["readiness"]["status"]) for s in manager.list() if s.session_id in saved]
    got = [(s["session_id"], s["paper_title"], s["created_at"], s["readiness"]) for s in manager.summaries() if s["session_id"] in saved]
    assert got == expected and len(got) == 40 and len(manager.sessions) == 0

    reads = []
    real = manager._read
    monkeypatch.setattr(type(manager), "_read", staticmethod(lambda path: reads.append(path.stem) or real(path)))
    assert len(manager.summaries()) >= 40 and reads == []  # unchanged files are not unpickled again

    session = real(manager._path(saved[0]))
    session.paper_title = "Renamed"
    manager.save(session)
    manager.sessions.clear()
    assert {s["session_id"]: s["paper_title"] for s in manager.summaries()}[saved[0]] == "Renamed"
    assert reads == [saved[0]]  # only the file that changed

    manager._path(saved[1]).unlink()
    assert saved[1] not in {s["session_id"] for s in manager.summaries()}
