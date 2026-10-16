"""`ask` honours --max-file-mb / --max-seconds like `analyze`: same wording, same exit codes."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _ask(*flags):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", SAMPLE, "Why calculus?", *flags],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_oversized_paper_is_refused_with_the_limit_exit_code():
    run = _ask("--max-file-mb", "0.0001")
    assert run.returncode == 123 and "limit exceeded" in run.stderr and "hint:" in run.stderr and run.stdout == ""


def test_generous_limits_still_answer():
    run = _ask("--max-file-mb", "5", "--max-seconds", "60")
    assert run.returncode == 0 and "Calculus" in run.stdout


def test_invalid_limit_is_refused_without_an_answer():
    run = _ask("--max-seconds", "-1")
    assert run.returncode != 0 and "greater than 0" in run.stderr and run.stdout == ""


def test_a_question_that_yields_no_answer_fails_instead_of_exiting_quietly(capsys):
    from types import SimpleNamespace

    from backend.cli_prerequisites import run_prerequisites_ask
    from backend.platform import platform as real

    stub = SimpleNamespace(
        analyze=lambda *a, **k: real.analyze(SAMPLE, **k),
        learning=SimpleNamespace(answer=lambda **k: {"responses": []}),
    )
    args = SimpleNamespace(paper=SAMPLE, question="anything", known=[], studied=[], as_json=False, max_seconds=None, max_file_mb=None)
    assert run_prerequisites_ask(args, platform=stub) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "no answer was produced" in captured.err
