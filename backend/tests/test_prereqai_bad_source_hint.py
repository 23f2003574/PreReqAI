"""A mistyped arXiv or DOI reference gets a hint showing what a valid one looks like, not the PDF-path hint."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]


def _analyze(source):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", source],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    return run.returncode, run.stderr + run.stdout


@pytest.mark.parametrize("source", ["arXiv:1706.037", "arxiv:", "https://arxiv.org/abs/1.1", "doi:10.1000", "10.1000/"])
def test_a_mistyped_reference_says_what_a_valid_one_looks_like(source):
    code, output = _analyze(source)
    assert code == 1
    assert "https://arxiv.org/abs/1706.03762" in output and "10.1000/xyz123" in output
    assert "must be a PDF file" not in output


@pytest.mark.parametrize("source", ["notes.txt", "my-doi-notes.txt", "examples"])
def test_other_unsupported_inputs_keep_the_pdf_hint(source):
    code, output = _analyze(source)
    assert code == 1
    assert "The paper must be a PDF file" in output and "arxiv.org/abs" not in output
