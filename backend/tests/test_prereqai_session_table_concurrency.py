"""Creating, evicting and deleting sessions on some request threads while others list them must not fail: the listing
returns a consistent snapshot, never "dictionary keys changed during iteration"."""
import sys
import threading

import pytest

from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai


def test_listing_sessions_while_others_are_created_and_evicted_does_not_fail():
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        manager = SessionManager()
        manager.MAX_SESSIONS_IN_MEMORY = 50
        errors = []

        def guarded(work):
            def run():
                try:
                    work()
                except Exception as exc:  # noqa: BLE001 - the failure is the assertion
                    errors.append(repr(exc))
            return run

        def create():
            for _ in range(1500):
                manager.delete(manager.create("paper").session_id) if _ % 7 == 0 else manager.create("paper")

        def listing():
            for _ in range(1500):
                manager.summaries()
                manager.list()

        threads = [threading.Thread(target=guarded(work)) for work in (create, create, listing, listing)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(previous)

    assert errors == []
    assert len(manager.sessions) <= 50
