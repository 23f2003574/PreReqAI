"""A paper title the console's encoding cannot represent (cp1252/ASCII consoles, redirects) prints escaped instead of crashing the CLI."""
import os
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]


def _paper(tmp_path):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), "Abstract\nWe study attention and neural networks.\n", fontsize=10)
    doc.set_metadata({"title": "Attention ∇ 日本語"})
    doc.save(path)
    return path


def test_analyze_survives_a_console_that_cannot_encode_the_title(tmp_path):
    plan = tmp_path / "plan.md"
    result = subprocess.run(
        [sys.executable, "-m", "backend.cli", "prerequisites", "analyze", str(_paper(tmp_path)), "--plan-file", str(plan)],
        capture_output=True, cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert result.returncode == 0, result.stderr.decode()
    assert b"Traceback" not in result.stderr
    assert b"\\u2207" in result.stdout  # escaped, not lost
    assert "∇" in plan.read_text(encoding="utf-8")  # the saved plan keeps the real characters
