"""The README quickstart works from a fresh checkout: the bundled sample paper
analyses successfully through the documented CLI command (the HTTP endpoint is
covered end to end by test_prereqai_entrypoint_smoke.py)."""
import json
from pathlib import Path

from backend.cli import EXIT_OK, main

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples" / "prerequisites" / "sample-paper.pdf"


def test_readme_quickstart_uses_the_bundled_sample_paper():
    readme = (ROOT / "README.md").read_text()
    assert "python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf" in readme
    assert SAMPLE.is_file()


def test_quickstart_cli_first_run_succeeds_with_the_documented_output(capsys):
    assert main(["prerequisites", "analyze", str(SAMPLE)]) == EXIT_OK
    assert capsys.readouterr().out.startswith("Analysed 'Attention Is All You Need (PreReqAI sample paper)'")

    assert main(["prerequisites", "analyze", str(SAMPLE), "--json"]) == EXIT_OK
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["status"] == "success" and outcome["report"]["concepts"]


def test_committed_sample_paper_matches_its_generator():
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_sample_paper", SAMPLE.with_name("make_sample_paper.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.build() == SAMPLE.read_bytes(), "run: python examples/prerequisites/make_sample_paper.py"


def test_human_summary_shows_the_study_plan_and_counts_only_unsatisfied_prerequisites(capsys):
    assert main(["prerequisites", "analyze", str(SAMPLE), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)["report"]
    assert main(["prerequisites", "analyze", str(SAMPLE)]) == EXIT_OK
    lines = capsys.readouterr().out.splitlines()

    missing = [item["concept"] for item in report["missing_prerequisites"] if not item["satisfied"]]
    covered = len(report["missing_prerequisites"]) - len(missing)
    assert covered > 0  # the sample paper covers one prerequisite itself
    assert f"  concepts: {len(report['concepts'])}  prerequisites: {len(report['prerequisites'])}  " \
           f"missing: {len(missing)} ({covered} covered in the paper)" in lines
    plan = [line for line in lines if line.startswith("  study plan: ")]
    assert len(plan) == 1 and all(f"{step['concept']} ({step['estimated_hours']}h)" in plan[0]
                                  for step in report["learning_plan"])
    assert {step["concept"] for step in report["learning_plan"]} <= set(missing)  # the plan covers what is missing
