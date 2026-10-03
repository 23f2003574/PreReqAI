"""Preflight at the boundary of the workflow. The CLI's input is a draft JSON
file (validated here before any generation work). Notebook dicts enter the
analysis pipeline through LLMNotebookAnalysisService, whose existing structure
check runs before any LLM request -- shown below -- so no second notebook
validator exists."""
import json
from dataclasses import asdict

import pytest

from backend.api_generation import InvalidDraftInputError, load_draft_file
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.notebook_analysis import InvalidNotebookError
from test_api_generation_boundary import _draft, _env
from test_llm_api_documentation_draft import ANALYSIS_RESPONSE, NOTEBOOK, build_env, make_response


@pytest.fixture
def draft_data():
    return asdict(_draft(_env())[1])


def _write(tmp_path, data, name="draft.json"):
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def test_a_valid_draft_loads_exactly_as_before(tmp_path, draft_data):
    assert asdict(load_draft_file(_write(tmp_path, draft_data))) == draft_data


def test_missing_input_unsupported_type_and_non_files_are_rejected(tmp_path, draft_data):
    (tmp_path / "dir.json").mkdir()
    cases = [
        (tmp_path / "missing.json", "no such file"),
        (tmp_path / "dir.json", "not a regular file"),
        (_write(tmp_path, draft_data, "draft.ipynb"), "unsupported input type '.ipynb'"),
        (_write(tmp_path, draft_data, "draft"), r"unsupported input type '\(no extension\)'"),
    ]
    for path, reason in cases:
        with pytest.raises(InvalidDraftInputError, match=reason):
            load_draft_file(path)


@pytest.mark.parametrize("content,reason", [("", "the file is empty"), ("{not json", "malformed JSON"), ("[1, 2]", "expected a JSON object")])
def test_empty_or_malformed_files_are_rejected(tmp_path, content, reason):
    with pytest.raises(InvalidDraftInputError, match=reason):
        load_draft_file(_write(tmp_path, content))


def test_structurally_incomplete_or_mistyped_drafts_name_every_problem(tmp_path, draft_data):
    incomplete = {k: v for k, v in draft_data.items() if k not in ("endpoint", "examples")}
    with pytest.raises(InvalidDraftInputError, match=r"missing fields \['endpoint', 'examples'\]"):
        load_draft_file(_write(tmp_path, incomplete))
    with pytest.raises(InvalidDraftInputError, match=r"unexpected fields \['extra'\]"):
        load_draft_file(_write(tmp_path, {**draft_data, "extra": 1}))

    mistyped = {**draft_data, "parameters": 5, "summary": "", "examples": {}, "status": "DONE"}
    with pytest.raises(InvalidDraftInputError) as raised:
        load_draft_file(_write(tmp_path, mistyped))
    message = str(raised.value)
    assert all(part in message for part in ("summary must be a non-empty string", "parameters must be a dict",
                                            "examples must be a list", "status must be one of"))


def test_cli_rejects_bad_input_at_the_input_stage_before_any_generation(tmp_path, draft_data, capsys):
    bad = _write(tmp_path, {**draft_data, "parameters": 5})

    code = main(["api-generation", "generate", "--draft", str(bad), "--output-dir", str(tmp_path / "o")])

    err = capsys.readouterr().err
    assert code == EXIT_FAILURE and "stage 'input': InvalidDraftInputError" in err and "parameters must be a dict" in err
    assert "Traceback" not in err and "AttributeError" not in err and not (tmp_path / "o").exists()


def test_cli_still_generates_from_a_valid_draft(tmp_path, draft_data):
    assert main(["api-generation", "generate", "--draft", str(_write(tmp_path, draft_data)), "--output-dir", str(tmp_path / "o")]) == EXIT_OK


@pytest.mark.parametrize("notebook", [None, {}, {"notebook_id": "n", "cells": []},
                                      {"notebook_id": "n", "cells": [{"cell_type": "code", "source": ["x = 1"]}]}])
def test_an_invalid_notebook_is_rejected_before_any_llm_request(notebook):
    env = build_env([make_response(ANALYSIS_RESPONSE)])
    provider = env["notebook_analysis"]._orchestration_service._providers["openai"]

    with pytest.raises(InvalidNotebookError):
        env["notebook_analysis"].analyze(notebook)

    assert provider.calls == 0


def test_a_valid_notebook_still_flows_into_analysis():
    env = build_env([make_response(ANALYSIS_RESPONSE)])

    analysis = env["notebook_analysis"].analyze(NOTEBOOK)

    assert [f["name"] for f in analysis.functions] == ["add"]
