"""Analysing a local PDF writes nothing into the current directory and works from a directory it cannot write to."""
import shutil
import subprocess
import sys
from pathlib import Path

from backend.ingestion.arxiv_resolver import ArxivResolver

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples/prerequisites/sample-paper.pdf"


def _analyze_from(workdir, *prepare):
    shutil.copy(SAMPLE, workdir / "paper.pdf")
    for name in prepare:
        (workdir / name).write_text("in the way")
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", "paper.pdf"],
                          cwd=workdir, env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
                          capture_output=True, text=True, timeout=120)


def test_local_analysis_leaves_the_working_directory_clean(tmp_path):
    run = _analyze_from(tmp_path)
    assert run.returncode == 0 and run.stderr == ""
    assert sorted(path.name for path in tmp_path.iterdir()) == ["paper.pdf"]


def test_a_file_named_cache_in_the_working_directory_no_longer_breaks_analysis(tmp_path):
    run = _analyze_from(tmp_path, "cache")
    assert run.returncode == 0 and "Analysed" in run.stdout and "Traceback" not in run.stderr


def test_download_still_creates_the_cache_directory_on_demand(tmp_path, monkeypatch):
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "deep" / "arxiv")
    monkeypatch.setattr(ArxivResolver, "_download", lambda self, url: b"%PDF-1.4 fake")
    resolver = ArxivResolver()
    assert not (tmp_path / "deep").exists()
    source = type("S", (), {"identifier": "1706.03762"})()
    assert Path(resolver.resolve(source)).read_bytes() == b"%PDF-1.4 fake"
