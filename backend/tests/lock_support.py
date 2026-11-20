"""Worker functions for the multi-process persistence tests (spawned processes import them by name)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def record_answers(path, worker, count):
    from backend import learner_profile

    for i in range(1, count + 1):
        learner_profile.record_quiz(path, f"Softmax:{worker * 1000 + i}", "Softmax", "knew")


def update_known(path, concepts):
    from backend import learner_profile

    for concept in concepts:
        learner_profile.update_profile(path, add_known=[concept])


def save_sessions(directory, worker, count):
    import os

    os.environ["PREREQAI_SESSION_DIR"] = str(directory)
    from backend.session.session_manager import SessionManager

    manager = SessionManager()
    for i in range(count):
        session = manager.create(paper_title=f"w{worker}-{i}", report={"paper": {"title": "t"}}, paper=None)
        manager.save(session)
        session.paper_title = f"w{worker}-{i}-again"
        manager.save(session)


def fill_cache(directory, key, rounds):
    import os

    os.environ["PREREQAI_ANALYSIS_CACHE_DIR"] = str(directory)
    from backend.analysis_cache import AnalysisCache
    from backend.models import Paper

    cache = AnalysisCache()
    for i in range(rounds):
        paper = Paper(source_path="x", metadata=None)
        cache._write_disk(key, {"paper": paper, "report": {"i": i, "pad": "x" * 5000}, "timings": {}})


def hold(path, seconds, ready):
    import time

    from backend.filelock import locked

    with locked(path):
        Path(ready).write_text("held")
        time.sleep(seconds)
