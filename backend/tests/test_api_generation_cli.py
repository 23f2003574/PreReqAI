import json
import subprocess
import sys
from dataclasses import asdict

import pytest

from backend.cli import EXIT_FAILURE, EXIT_OK, main
from test_api_generation_boundary import _draft, _env


@pytest.fixture
def drafts(tmp_path):
    """(validated draft file, unvalidated draft file) written as JSON."""
    env = _env()
    draft, validated = _draft(env)
    paths = []
    for name, value in (("validated.json", validated), ("draft.json", draft)):
        path = tmp_path / name
        path.write_text(json.dumps(asdict(value)))
        paths.append(path)
    return paths


def test_generate_writes_the_project_and_prints_a_human_summary(tmp_path, drafts, capsys):
    out = tmp_path / "project"

    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(out)])

    text = capsys.readouterr().out
    assert code == EXIT_OK and "Generated POST /add" in text and "uvicorn app.main:app" in text
    assert (out / "app" / "main.py").is_file() and (out / "openapi.json").is_file()


def test_json_output_is_the_machine_readable_result(tmp_path, drafts, capsys):
    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "p"), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK and payload["endpoint"] == "POST /add"
    assert payload["files"] == ["Dockerfile", "README.md", "app/__init__.py", "app/main.py", "openapi.json", "prereqai-config.json", "prereqai-manifest.json", "prereqai-project.json", "requirements.txt"]


def test_unvalidated_draft_fails_naming_the_stage_and_writes_nothing(tmp_path, drafts, capsys):
    code = main(["api-generation", "generate", "--draft", str(drafts[1]), "--output-dir", str(tmp_path / "p")])

    err = capsys.readouterr().err
    assert code == EXIT_FAILURE and "stage 'generation'" in err and "DraftNotValidatedError" in err
    assert "Traceback" not in err and not (tmp_path / "p").exists()


def test_unsupported_endpoint_is_reported_without_a_stack_trace(tmp_path, drafts, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**json.loads(drafts[0].read_text()), "endpoint": "FETCH /add"}))

    code = main(["api-generation", "generate", "--draft", str(bad), "--output-dir", str(tmp_path / "p")])

    err = capsys.readouterr().err
    assert code == EXIT_FAILURE and "InvalidDraftEndpointError" in err and "Traceback" not in err


@pytest.mark.parametrize("content", [None, "not json", '{"draft_id": "x"}'])
def test_missing_or_malformed_draft_file_is_a_clean_error(tmp_path, capsys, content):
    path = tmp_path / "d.json"
    if content is not None:
        path.write_text(content)

    code = main(["api-generation", "generate", "--draft", str(path), "--output-dir", str(tmp_path / "p")])

    err = capsys.readouterr().err
    assert code == EXIT_FAILURE and "stage 'input'" in err and "cannot read a draft" in err


def test_runs_as_a_module_and_the_generated_project_imports(tmp_path, drafts):
    out = tmp_path / "project"
    run = subprocess.run(
        [sys.executable, "-m", "backend.cli", "api-generation", "generate", "--draft", str(drafts[0]),
         "--output-dir", str(out)], capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stderr
    probe = subprocess.run([sys.executable, "-c", "from app.main import app"], cwd=out, capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr
