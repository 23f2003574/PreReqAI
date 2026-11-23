"""The analysis cache key follows the source that produces an analysis, so a cache written by older code is never served after the code changes."""
import pytest

from backend import analysis_cache

pytestmark = pytest.mark.prereqai


def tree(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_the_fingerprint_changes_when_a_listed_source_file_is_edited_added_or_removed(tmp_path):
    root = tree(tmp_path, {"parsing/a.py": "x = 1\n", "prerequisites/graph.json": "{}", "evidence.py": "y = 1\n"})
    before = analysis_cache.source_fingerprint(root)
    assert analysis_cache.source_fingerprint(root) == before
    (root / "parsing/a.py").write_text("x = 2\n")
    edited = analysis_cache.source_fingerprint(root)
    (root / "ingestion").mkdir()
    (root / "ingestion/new.py").write_text("z = 1\n")
    added = analysis_cache.source_fingerprint(root)
    (root / "ingestion/new.py").unlink()
    assert len({before, edited, added}) == 3 and analysis_cache.source_fingerprint(root) == edited
    (root / "prerequisites/graph.json").write_text('{"rules": []}')
    assert analysis_cache.source_fingerprint(root) != edited


def test_unrelated_packages_caches_and_tests_do_not_change_the_fingerprint(tmp_path):
    root = tree(tmp_path, {"parsing/a.py": "x = 1\n"})
    before = analysis_cache.source_fingerprint(root)
    tree(root, {"tutor/quiz.py": "q = 1\n", "parsing/__pycache__/a.cpython-313.pyc": "junk", "parsing/notes.md": "text", "tests/test_x.py": "t = 1\n"})
    assert analysis_cache.source_fingerprint(root) == before


def test_the_real_fingerprint_covers_the_files_that_shape_the_report():
    covered = analysis_cache.source_fingerprint()
    assert len(covered) == 16 and covered == analysis_cache.source_fingerprint()


def test_a_changed_fingerprint_makes_a_cached_file_a_different_key(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 same bytes")
    first = analysis_cache.file_key(pdf)
    monkeypatch.setattr(analysis_cache, "_fingerprint", lambda: "another-source-version")
    second = analysis_cache.file_key(pdf)
    assert first.split("-")[0] == second.split("-")[0] and first != second
