"""`prerequisites analyze --tree` prints the prerequisite tree, and the help says arXiv/DOI sources are accepted."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_tree_flag_prints_the_chain_with_known_and_studied_marks():
    run = _cli(SAMPLE, "--tree", "--known", "Calculus", "--studied", "Linear Algebra")
    lines = run.stdout.splitlines()

    assert run.returncode == 0 and "  prerequisite tree:" in lines
    assert "    - Transformer" in lines and "      - Attention (known or covered)" in lines
    assert "        - Linear Algebra (studied)" in lines and "      - Calculus (known or covered)" in lines


def test_summary_has_no_tree_unless_asked():
    assert "prerequisite tree" not in _cli(SAMPLE).stdout


def test_help_names_arxiv_and_doi_sources():
    help_text = _cli("--help").stdout
    assert "arXiv" in help_text and "DOI" in help_text and "--tree" in help_text
