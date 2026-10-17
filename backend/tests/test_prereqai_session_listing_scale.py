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
