"""Two workers changing one saved session do not lose each other's updates: versions, merge of independent fields, real conflicts, legacy files."""
import json
import multiprocessing
from types import SimpleNamespace

import pytest

from backend.platform import platform
from backend.platform.prereqai_platform import KNOWN_REASON
from backend.progress import StudyProgressTracker
from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    directory = tmp_path_factory.mktemp("sessions")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PREREQAI_SESSION_DIR", str(directory))
        yield directory, platform.analyze(SAMPLE)["session_id"]


@pytest.fixture
def workers(saved, monkeypatch):
    directory, sid = saved
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(directory))
    first, second = SessionManager(), SessionManager()
    return sid, first, second, first.get(sid), second.get(sid)


def _study(session, concept):
    StudyProgressTracker().complete(session.paper, concept)
    platform._refresh_progress(session.paper, session.report)


def _studied(session):
    return {item.concept for item in session.paper.study_progress if item.completed}


def _plan(session):
    return [item.concept for item in session.paper.study_progress]


def test_every_save_advances_the_version(workers):
    sid, first, _, a, _ = workers
    before = a.version
    first.save(a)
    assert a.version == before + 1 and SessionManager._read(first._path(sid)).version == a.version


def test_independent_changes_from_two_workers_are_both_kept(workers):
    sid, first, second, a, b = workers
    plan = _plan(a)
    assert len(plan) >= 3
    _study(a, plan[0])
    a.dismissed_suggestions = [plan[1]]
    a.plan_start = "2026-01-05"
    a.quiz_attempts.append({"question_id": "qa", "concept": plan[0], "outcome": "correct", "revealed": False})
    _study(b, plan[2])
    b.quiz_attempts.append({"question_id": "qb", "concept": plan[2], "outcome": "wrong", "revealed": True})
    first.save(a)
    second.save(b)  # stale: the file already holds worker A's version
    merged = SessionManager._read(second._path(sid))
    assert {plan[0], plan[2]} <= _studied(merged) and _studied(b) == _studied(merged)
    assert merged.dismissed_suggestions == [plan[1]] and merged.plan_start == "2026-01-05"
    assert [item["question_id"] for item in merged.quiz_attempts][-2:] == ["qa", "qb"]
    assert merged.version > a.version >= 1 and second.last_conflicts == []


def test_marking_known_in_one_worker_and_studying_in_another_merge(workers):
    sid, first, second, a, b = workers
    plan = _plan(a)
    known = next(name for name in plan if name not in _studied(a))
    other = next(name for name in plan if name != known and name not in _studied(a))
    target = SimpleNamespace(paper=a.paper, report=a.report)
    platform._personalize(target, [known], [])
    _study(b, other)
    first.save(a)
    second.save(b)
    merged = SessionManager._read(second._path(sid))
    assert known in {item.concept for item in merged.paper.missing_prerequisites if item.reason == KNOWN_REASON}
    assert other in _studied(merged) and known not in _plan(merged)


def test_two_different_plan_starts_are_a_conflict_and_the_saving_worker_wins(workers):
    sid, first, second, a, b = workers
    a.plan_start, b.plan_start = "2026-02-01", "2026-03-01"
    first.save(a)
    second.save(b)
    assert any("plan_start" in item for item in second.last_conflicts)
    assert SessionManager._read(second._path(sid)).plan_start == "2026-03-01"


def test_a_legacy_session_without_a_version_is_readable_and_saved_with_one(saved, tmp_path, monkeypatch):
    directory, sid = saved
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    manager = SessionManager()
    source = (directory / f"{sid}.session").read_text()
    document = json.loads(source)
    stripped = json.dumps(document).replace('"version"', '"version_removed"') if '"version"' in source else source
    (tmp_path / f"{sid}.session").write_text(stripped)
    session = manager.get(sid)
    assert session is not None and session.version == 0
    manager.save(session)
    assert SessionManager._read(manager._path(sid)).version == 1


def _study_in_a_process(directory, sid, concept):
    import os
    os.environ["PREREQAI_SESSION_DIR"] = directory
    manager = SessionManager()
    session = manager.get(sid)
    _study(session, concept)
    session.quiz_attempts.append({"question_id": f"q-{concept}", "concept": concept, "outcome": "correct", "revealed": False})
    manager.save(session)


def test_processes_saving_at_once_keep_every_update(saved, tmp_path, monkeypatch):
    directory, sid = saved
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    (tmp_path / f"{sid}.session").write_bytes((directory / f"{sid}.session").read_bytes())
    start = SessionManager().get(sid)
    concepts = [name for name in _plan(start) if name not in _studied(start)][:4]
    assert len(concepts) >= 3
    context = multiprocessing.get_context("fork")
    workers = [context.Process(target=_study_in_a_process, args=(str(tmp_path), sid, name)) for name in concepts]
    [worker.start() for worker in workers]
    [worker.join(120) for worker in workers]
    assert all(worker.exitcode == 0 for worker in workers)
    final = SessionManager._read(SessionManager()._path(sid))
    assert set(concepts) <= _studied(final)
    assert {item["question_id"] for item in final.quiz_attempts} >= {f"q-{name}" for name in concepts}
    assert final.version >= start.version + len(concepts)
