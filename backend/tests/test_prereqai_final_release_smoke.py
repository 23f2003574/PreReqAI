"""Final release smoke: the primary entry point run as a user runs it -- a fresh
`python -m backend.cli` process from the repository root, no in-process state.
One representative success (the README quickstart, human and --json output) and
one representative invalid input (a corrupt PDF) must each reach their expected
final user-facing output and exit code."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "backend.cli", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=120)


def test_quickstart_succeeds_with_the_documented_human_and_json_output():
    human = _cli("prerequisites", "analyze", SAMPLE)
    assert human.returncode == 0 and human.stderr == ""
    assert human.stdout.startswith("Analysed 'Attention Is All You Need (PreReqAI sample paper)' (session ")
    assert "concepts: " in human.stdout and "prerequisites: " in human.stdout
    assert "  missing: 3 (1 covered in the paper)" in human.stdout  # only unsatisfied prerequisites count
    assert "\n  study plan: 1. " in human.stdout and len(human.stdout.splitlines()) <= 4

    machine = _cli("prerequisites", "analyze", SAMPLE, "--json")
    outcome = json.loads(machine.stdout)
    assert machine.returncode == 0 and outcome["status"] == "success" and outcome["stage"] == "session_created"
    assert outcome["session_id"] and outcome["report"]["concepts"] and outcome["warnings"] == []


def test_corrupt_paper_fails_with_one_actionable_error_and_exit_code_1(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")

    result = _cli("prerequisites", "analyze", str(bad))

    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.startswith("error: analysis failed at stage 'analysis': Failed to process the uploaded paper")
    assert "  hint: Upload a text-based PDF research paper." in result.stderr and "Traceback" not in result.stderr


def test_a_mistyped_paper_path_is_reported_as_a_path_problem(tmp_path):
    result = _cli("prerequisites", "analyze", str(tmp_path / "nope.pdf"))

    assert result.returncode == 1 and result.stdout == "" and "Traceback" not in result.stderr
    assert "  hint: Check the paper path: it must name an existing PDF file" in result.stderr
