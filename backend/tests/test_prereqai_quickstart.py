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

    # Compare content, not bytes: PDF bytes vary across the PyMuPDF versions
    # requirements.txt allows, so a byte check would fail in a fresh environment.
    import pymupdf

    def content(data):
        with pymupdf.open(stream=data, filetype="pdf") as document:
            return document.page_count, [page.get_text() for page in document], document.metadata["title"]

    assert content(module.build()) == content(SAMPLE.read_bytes()), \
        "run: python examples/prerequisites/make_sample_paper.py"


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


def test_readme_documented_limit_flags_work_and_exceeding_them_exits_123(capsys):
    assert "prerequisites analyze my-paper.pdf --max-file-mb 20 --max-seconds 60" in (ROOT / "README.md").read_text()
    assert main(["prerequisites", "analyze", str(SAMPLE), "--max-file-mb", "20", "--max-seconds", "60"]) == EXIT_OK
    capsys.readouterr()
    assert main(["prerequisites", "analyze", str(SAMPLE), "--max-file-mb", "0.0001"]) == 123


def test_cli_and_api_report_the_same_single_version(capsys):
    import pytest
    from backend.main import app
    from backend.version import __version__

    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"PreReqAI {__version__}"
    assert app.version == __version__


def test_missing_dependency_gives_a_clean_error_not_a_traceback(monkeypatch, capsys):
    import sys

    for name in [n for n in sys.modules if n == "backend.platform" or n.startswith("backend.platform.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "pymupdf", None)  # makes `import pymupdf` raise ModuleNotFoundError

    assert main(["prerequisites", "analyze", str(SAMPLE)]) == 1
    err = capsys.readouterr().err
    assert "required package 'pymupdf' is not installed" in err
    assert "pip install -r requirements.txt" in err


def test_readme_http_contract_matches_the_endpoints():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with SAMPLE.open("rb") as pdf:
        ok = client.post("/api/prerequisites/analyze", files={"paper": ("s.pdf", pdf, "application/pdf")})
    assert ok.status_code == 200 and {"status", "session_id", "report", "timings", "warnings"} <= set(ok.json())
    bad = client.post("/api/prerequisites/analyze", files={"paper": ("x.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 400 and bad.json()["status"] == "failure"
    assert client.post("/api/prerequisites/analyze").status_code == 422

    sid = ok.json()["session_id"]
    assert client.get(f"/api/session/{sid}").status_code == 200
    assert client.get("/api/session/nope").status_code == 404
    assert client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"}).status_code == 200
    assert client.post(f"/api/session/{sid}/question", json={"question": " "}).status_code == 422
    assert client.post("/api/session/nope/question", json={"question": "q"}).status_code == 404


def test_example_workflow_analyse_then_ask_a_question():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with SAMPLE.open("rb") as pdf:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("s.pdf", pdf, "application/pdf")}).json()["session_id"]
    reply = client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"}).json()
    assert reply["status"] == "success" and reply["responses"]
    assert reply["responses"][0]["supporting_concepts"] == ["Attention"]
    assert "tutoring model has not yet been configured" in reply["responses"][0]["answer"]  # documented placeholder
