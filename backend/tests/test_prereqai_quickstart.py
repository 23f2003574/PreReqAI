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
