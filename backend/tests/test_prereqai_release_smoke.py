"""PreReqAI end-to-end release smoke: one real tiny paper driven through the
supported entrypoints (the `prerequisites analyze` CLI and POST
/api/prerequisites/analyze) across every terminal path -- success, invalid
input and configuration, ordinary failure, cancellation, timeout, resource
limit -- each followed by a successful run that must equal the baseline, so
no failed or interrupted run can contaminate the next one. Only the arXiv
download is mocked (it needs the network)."""
import json
import os
import signal

import fitz
import requests
from fastapi.testclient import TestClient

import backend.ingestion.arxiv_resolver as arxiv_resolver
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.cli_common import EXIT_CANCELLED, EXIT_LIMIT_EXCEEDED, EXIT_TIMEOUT
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

client = TestClient(app)


def _paper(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return path


def _cli(capsys, *args):
    code = main(["prerequisites", "analyze", *args])
    captured = capsys.readouterr()
    return code, captured


def _cli_json(capsys, *args):
    code, captured = _cli(capsys, *args, "--json")
    return code, json.loads(captured.out)


def test_every_terminal_path_behaves_and_never_contaminates_the_next_run(tmp_path, capsys, monkeypatch):
    paper = _paper(tmp_path)
    garbage = tmp_path / "garbage.pdf"
    garbage.write_bytes(b"not a pdf")
    resolver = platform.analysis.source_resolver._resolvers["arxiv"]
    monkeypatch.setattr(resolver, "CACHE_DIRECTORY", tmp_path / "cache")
    (tmp_path / "cache").mkdir()

    # 1. success through both surfaces; this is the baseline every later success must equal
    code, baseline = _cli_json(capsys, str(paper), "--diagnose")
    api = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", paper.read_bytes(), "application/pdf")})
    assert code == EXIT_OK and baseline["status"] == "success" and baseline["stage"] == "session_created"
    assert api.status_code == 200 and api.json()["report"] == baseline["report"]
    assert baseline["diagnostics"]["failed_after"] is None and baseline["warnings"] == []
    sessions = len(session_manager.sessions)

    def still_clean(label):
        code, again = _cli_json(capsys, str(paper))  # a successful run after the failed/interrupted one
        assert code == EXIT_OK and again["report"] == baseline["report"], label
        assert again["session_id"] != baseline["session_id"]
        assert len(session_manager.sessions) == sessions + 1, label  # only the success opened a session
        session_manager.sessions.pop(again["session_id"], None)

    # 2. invalid input / invalid configuration
    code, bad_input = _cli_json(capsys, str(tmp_path / "missing.pdf"))
    assert code == EXIT_FAILURE and bad_input["status"] == "failure" and bad_input["stage"] == "analysis"
    still_clean("invalid input")
    code, bad_config = _cli_json(capsys, str(paper), "--max-seconds", "0")
    assert code == EXIT_FAILURE and bad_config["status"] == "failure" and bad_config["stage"] == "configuration"
    still_clean("invalid configuration")

    # 3. ordinary pipeline failure (a file that is not a PDF), through the CLI and the API
    code, failed = _cli_json(capsys, str(garbage))
    api_failed = client.post("/api/prerequisites/analyze", files={"paper": ("g.pdf", garbage.read_bytes(), "application/pdf")})
    assert code == EXIT_FAILURE and failed["status"] == "failure" and api_failed.status_code == 400
    assert api_failed.json()["status"] == "failure" and set(api_failed.json()) == set(failed)
    still_clean("pipeline failure")

    # 4. cancellation: a real Ctrl-C during a stage stops the run before the next stage
    parser = platform.analysis.section_parser
    real_parse = parser.parse
    monkeypatch.setattr(parser, "parse", lambda document: (os.kill(os.getpid(), signal.SIGINT), real_parse(document))[1])
    code, cancelled = _cli_json(capsys, str(paper), "--diagnose")
    monkeypatch.setattr(parser, "parse", real_parse)
    assert code == EXIT_CANCELLED and cancelled["status"] == "cancelled" and cancelled["diagnostics"]["stopped_after"] == "section_parser"
    assert "report" not in cancelled and "session_id" not in cancelled
    still_clean("cancellation")

    # 5. timeout of the (mocked) download
    monkeypatch.setattr(arxiv_resolver.requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.ReadTimeout("slow")))
    code, timed_out = _cli_json(capsys, "https://arxiv.org/abs/9999.00001")
    assert code == EXIT_TIMEOUT and timed_out["status"] == "timeout" and not list((tmp_path / "cache").iterdir())
    still_clean("timeout")

    # 6. resource-budget termination
    code, limited = _cli_json(capsys, str(paper), "--max-file-mb", "0.00001")
    assert code == EXIT_LIMIT_EXCEEDED and limited["status"] == "limit_exceeded" and "session_id" not in limited
    still_clean("resource limit")

    # every non-success is a valid, distinct terminal state carrying no output
    statuses = [r["status"] for r in (bad_input, bad_config, failed, cancelled, timed_out, limited)]
    assert statuses == ["failure", "failure", "failure", "cancelled", "timeout", "limit_exceeded"]
    assert all(not ({"session_id", "report", "timings"} & set(r)) for r in (bad_input, bad_config, failed, cancelled, timed_out, limited))
