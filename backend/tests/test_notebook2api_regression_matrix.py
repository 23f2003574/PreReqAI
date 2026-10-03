"""Release-path regression matrix for the supported Notebook2API workflow.
One scenario table drives the real CLI (`api-generation generate/check`) on the
committed example; two extra tests cover the notebook -> draft -> project path
that has no CLI entry. Everything asserted is public behavior: exit status, the
--json result, and files on disk."""
import json
import shutil
from pathlib import Path

import pytest

from backend.api_generation import generate_application
from backend.cli import (
    EXIT_FAILURE,
    EXIT_INVALID_INPUT,
    EXIT_OK,
    EXIT_USAGE,
    main,
)
from backend.notebook_analysis import InvalidNotebookError
from test_api_generation_boundary import _draft, _env
from test_llm_api_documentation_draft import NOTEBOOK, build_env

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "api-generation" / "draft.json"


def _prepare(tmp_path, kind):
    """(extra generate args, output dir) for a scenario kind."""
    out = tmp_path / "out"
    draft = tmp_path / "draft.json"
    data = json.loads(EXAMPLE.read_text())
    if kind == "bad-types":
        draft.write_text(json.dumps({**data, "parameters": 5}))
    elif kind == "unvalidated":
        draft.write_text(json.dumps({**data, "status": "DRAFT"}))
    elif kind == "missing-draft":
        draft = tmp_path / "nope.json"
    else:
        shutil.copy(EXAMPLE, draft)
    args = ["--draft", str(draft), "--output-dir", str(out)]
    if kind == "bad-config":
        args += ["--port", "0"]
    if kind == "dry-run":
        args += ["--dry-run"]
    if kind == "file-target":
        out.write_text("a file, not a directory")
    if kind == "under-file":
        (tmp_path / "blocker").write_text("a file")
        args[args.index("--output-dir") + 1] = str(tmp_path / "blocker" / "project")
    if kind == "collision":
        out.mkdir()
        (out / "Dockerfile").write_text("the user's own")
    return args, out


# kind -> (exit code, status, failed stage, whether output must be written)
GENERATE_SCENARIOS = {
    "valid": (EXIT_OK, "success", None, True),
    "dry-run": (EXIT_OK, "success", None, False),
    "missing-draft": (EXIT_INVALID_INPUT, "failed", "input", False),
    "bad-types": (EXIT_INVALID_INPUT, "failed", "input", False),
    "unvalidated": (EXIT_INVALID_INPUT, "failed", "generation", False),
    "bad-config": (EXIT_INVALID_INPUT, "failed", "configuration", False),
    "file-target": (EXIT_INVALID_INPUT, "failed", "configuration", False),
    "under-file": (EXIT_INVALID_INPUT, "failed", "preflight", False),
    "collision": (EXIT_INVALID_INPUT, "failed", "write", False),
}


@pytest.mark.parametrize("kind", sorted(GENERATE_SCENARIOS))
def test_generate_scenarios(tmp_path, capsys, kind):
    code, status, stage, written = GENERATE_SCENARIOS[kind]
    args, out = _prepare(tmp_path, kind)

    actual = main(["api-generation", "generate", *args, "--json"])

    captured = capsys.readouterr()
    result = json.loads(captured.out)  # always exactly one JSON document, even on failure
    assert actual == code and result["status"] == status and "Traceback" not in captured.err
    assert result.get("failed_stage") == stage
    if status == "success":
        assert result["validation"] == "passed" and result["dry_run"] == (kind == "dry-run")
    else:
        assert result["validation"] == ("passed" if stage == "write" else "not run") and "files" not in result
    if written:
        assert all((out / path).is_file() for path in result["files"])
    elif kind == "collision":
        assert sorted(p.name for p in out.iterdir()) == ["Dockerfile"] and (out / "Dockerfile").read_text() == "the user's own"
    elif kind not in ("file-target", "under-file"):
        assert not out.exists()


def test_usage_error_exits_with_the_usage_code():
    with pytest.raises(SystemExit) as raised:
        main(["api-generation", "generate", "--output-dir", "x"])
    assert raised.value.code == EXIT_USAGE


def _generated(tmp_path):
    args, out = _prepare(tmp_path, "valid")
    assert main(["api-generation", "generate", *args, "-q"]) == EXIT_OK
    return out


def _break_app(out):
    (out / "app" / "main.py").write_text("def broken(:\n")


def _make_incompatible(out):
    path = out / "prereqai-project.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "contract_version": 99}))


# mutation -> (exit code, health status)
CHECK_SCENARIOS = {
    "healthy": (None, EXIT_OK, "healthy"),
    "broken application": (_break_app, EXIT_FAILURE, "invalid"),
    "incompatible project": (_make_incompatible, EXIT_FAILURE, "incompatible"),
    "not a project": (lambda out: shutil.rmtree(out), EXIT_FAILURE, "invalid"),
}


@pytest.mark.parametrize("name", sorted(CHECK_SCENARIOS))
def test_check_scenarios(tmp_path, capsys, name):
    mutate, code, status = CHECK_SCENARIOS[name]
    out = _generated(tmp_path)
    capsys.readouterr()
    if mutate:
        mutate(out)

    actual = main(["api-generation", "check", str(out), "--json"])

    assert actual == code and json.loads(capsys.readouterr().out)["status"] == status


def test_valid_notebook_reaches_a_validated_draft_and_then_a_healthy_project(tmp_path, capsys):
    env = _env()  # scripted LLM: notebook analysis -> candidates -> schemas -> recommendation -> review -> draft
    draft, validated = _draft(env)
    assert validated.status == "VALIDATED" and validated.endpoint == "POST /add"

    application = generate_application(env["draft"], validated, tmp_path / "out")

    assert main(["api-generation", "check", str(application.output_dir), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "healthy" and draft.status == "DRAFT"


def test_invalid_notebook_input_fails_cleanly_before_analysis_and_a_valid_one_is_analysed():
    env = build_env([])
    with pytest.raises(InvalidNotebookError):
        env["notebook_analysis"].analyze({"notebook_id": "n", "cells": []})
    assert NOTEBOOK["cells"] and NOTEBOOK["notebook_id"]
