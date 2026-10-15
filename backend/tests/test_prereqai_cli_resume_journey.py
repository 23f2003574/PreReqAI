"""Acceptance: a learner works through the plan from the command line alone. The CLI keeps no state, so each step
re-runs the same paper with more --studied flags; the summary, the study links and `ask` must agree at every step."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PLAN = ["Linear Algebra", "Probability", "Calculus", "Neural Networks"]


def _run(*args):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def _studied_flags(done):
    return [flag for name in done for flag in ("--studied", name)]


def _links(out):
    return [line.split(":")[0].strip() for line in out.splitlines() if line.startswith("    ")]


def test_learner_works_through_the_plan_from_the_command_line():
    done = []
    for step, concept in enumerate(PLAN, start=1):
        remaining = PLAN[step - 1:]
        run = _run("analyze", SAMPLE, "--resources", *_studied_flags(done))
        assert run.returncode == 0 and run.stderr == ""
        assert _links(run.stdout) == remaining                     # links shrink in plan order
        assert f"({len(done)}/4 concepts ready)" in run.stdout
        asked = _run("ask", SAMPLE, "What should I learn first?", *_studied_flags(done))
        assert asked.returncode == 0 and asked.stdout.splitlines()[0].startswith(f"Study these in order before the paper: {step}. {concept}")
        done.append(concept)

    finished = _run("analyze", SAMPLE, "--resources", *_studied_flags(done), "--json")
    report = json.loads(finished.stdout)["report"]
    assert report["readiness"]["ready_to_read"] is True and report["readiness"]["completed_concepts"] == 4
    plain = _run("analyze", SAMPLE, "--resources", *_studied_flags(done))
    assert "Ready to Read" in plain.stdout and "resources: none left to study" in plain.stdout and "(0h left)" in plain.stdout
    assert "ready to read the paper" in _run("ask", SAMPLE, "What should I learn first?", *_studied_flags(done)).stdout


def test_mistakes_midway_are_reported_without_losing_progress(tmp_path):
    typo = _run("analyze", SAMPLE, "--resources", "--studied", "Probabilty", "--studied", "Calculus")
    assert typo.returncode == 0
    assert "--studied 'Probabilty' is not in this paper's study plan and was ignored" in typo.stdout
    assert "Calculus (10h, studied)" in typo.stdout and "Probability:" in typo.stdout and "Calculus:" not in typo.stdout

    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 not really")
    failed = _run("analyze", str(broken), "--resources", "--studied", "Calculus")
    assert failed.returncode == 1 and "resources" not in failed.stdout and failed.stderr.startswith("error:")
    assert _run("analyze", SAMPLE, "--resources", "--studied", "Calculus").returncode == 0  # the next run is unaffected
