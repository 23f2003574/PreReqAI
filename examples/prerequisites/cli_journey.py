"""Runnable command-line study journey on the sample paper, offline, no server or API keys.

From the repository root:  python examples/prerequisites/cli_journey.py

The CLI keeps no state between runs, so the saved Markdown plan is the state: analyse and save the plan, tick the
concept you finished in that file (here the script edits it, as you would in an editor), then re-run with --resume.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def cli(*args):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", *args], cwd=ROOT, capture_output=True, text=True)
    if run.returncode != 0:
        raise SystemExit(f"command failed ({run.returncode}): {run.stderr}")
    return run.stdout


def main() -> int:
    with tempfile.TemporaryDirectory() as folder:
        plan = Path(folder) / "plan.md"

        print("1. Analyse (Calculus is already known) and save the plan\n")
        print(cli("analyze", SAMPLE, "--known", "Calculus", "--plan-file", str(plan)))
        print(plan.read_text(encoding="utf-8"))

        print("2. Finish Linear Algebra: tick its box in plan.md\n")
        text = plan.read_text(encoding="utf-8")
        assert "- [ ] 1. Linear Algebra" in text
        plan.write_text(text.replace("- [ ] 1. Linear Algebra", "- [x] 1. Linear Algebra"), encoding="utf-8")

        print("3. Re-run with --resume: the ticked concept is studied again, and the same file is updated\n")
        print(cli("analyze", SAMPLE, "--known", "Calculus", "--resume", str(plan), "--plan-file", str(plan)))

        print("4. Ask a question from the same progress\n")
        print(cli("ask", SAMPLE, "What should I learn first?", "--known", "Calculus", "--resume", str(plan)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
