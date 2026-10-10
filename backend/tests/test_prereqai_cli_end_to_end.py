"""End-to-end smoke test of the real user-facing path, run as the user runs it:
`python -m backend.cli prerequisites analyze ...` in its own process, from
input and option validation through the workflow to the canonical result, the
CLI's text/JSON output and the process exit status. Timeout and cancellation
need an injected condition, so those two go through the same CLI entrypoint
in-process with the existing mocking conventions."""
import json
import subprocess
import sys
from pathlib import Path

import pymupdf as fitz
import pytest

from backend.cli import main
from backend.cli_common import EXIT_CANCELLED, EXIT_FAILURE, EXIT_LIMIT_EXCEEDED, EXIT_OK, EXIT_TIMEOUT, EXIT_USAGE
from backend.platform import platform

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def paper(tmp_path_factory):
    document = fitz.open()
    document.new_page().insert_text(
        (72, 72), "Attention Is All You Need\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11
    )
    path = tmp_path_factory.mktemp("cli") / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _cli(*args):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", *args],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    return run.returncode, run.stdout, run.stderr


def test_valid_input_succeeds_with_a_summary_and_a_canonical_json_result(paper):
    code, out, err = _cli(paper)
    assert code == EXIT_OK and out.startswith("Analysed '") and "concepts:" in out and "warning:" not in out
    assert "Traceback" not in err

    code, out, _ = _cli(paper, "--json")
    result = json.loads(out)
    assert code == EXIT_OK and result["status"] == "success" and result["warnings"] == []
    assert result["session_id"] and set(result["report"]) >= {"concepts", "prerequisites", "learning_plan"}
    assert list(result["timings"])[0] == "source_detector" and list(result["timings"])[-1] == "report_generator"


@pytest.mark.parametrize("args, code, message", [
    (["see https://arxiv.org/abs/1706.03762 and 10.1000/xyz"], EXIT_FAILURE, "Unsupported research source"),
    (["{paper}", "--max-seconds", "-1"], EXIT_FAILURE, "at stage 'configuration'"),
    (["{paper}", "--max-file-mb", "0.0001"], EXIT_LIMIT_EXCEEDED, "limit exceeded"),
])
def test_invalid_input_or_configuration_fails_cleanly(paper, args, code, message):
    exit_code, out, err = _cli(*[arg.format(paper=paper) for arg in args])

    assert exit_code == code and out == "" and message in err and "hint:" in err and "Traceback" not in err


def test_a_usage_error_is_reported_by_the_parser():
    exit_code, out, err = _cli()

    assert exit_code == EXIT_USAGE and out == "" and "paper" in err


def test_a_workflow_failure_on_a_broken_pdf_fails_with_its_stage_and_exit_code(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 truncated")

    code, out, err = _cli(str(broken), "--diagnose")
    assert code == EXIT_FAILURE and out == "" and "Traceback" not in err
    assert "analysis failed at stage 'analysis'" in err and "failed after source_resolver" in err

    code, out, _ = _cli(str(broken), "--json")
    result = json.loads(out)
    assert code == EXIT_FAILURE and result["status"] == "failure" and result["error"]["type"] and "report" not in result


def test_timeout_and_cancellation_reach_the_cli_as_their_own_exit_codes(paper, capsys, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(platform.analysis.ingestion, "ingest", lambda path: (_ for _ in ()).throw(TimeoutError("slow")))
        assert main(["prerequisites", "analyze", paper]) == EXIT_TIMEOUT
    assert "error: timed out at stage 'analysis'" in capsys.readouterr().err

    with monkeypatch.context() as patch:
        patch.setattr(platform.analysis.section_parser, "parse", lambda document: (_ for _ in ()).throw(KeyError("never reached")))
        patch.setattr("threading.Event.is_set", lambda self: True)  # as if Ctrl-C was pressed before the first stage
        assert main(["prerequisites", "analyze", paper, "--json"]) == EXIT_CANCELLED
    assert json.loads(capsys.readouterr().out)["status"] == "cancelled"

    assert main(["prerequisites", "analyze", paper]) == EXIT_OK  # nothing carried over
