"""Representative failure paths of the supported Notebook2API entrypoint share
one error format: failed stage, exception type and reason, underlying cause,
an actionable hint -- and never a raw traceback."""
import json
from dataclasses import asdict

import pytest

from backend.api_generation import FastAPIApplicationGenerator
from backend.cli import EXIT_GENERATION_FAILED, EXIT_INVALID_INPUT, main
from test_api_generation_boundary import _draft, _env


def _fail(capsys, *args, code=EXIT_INVALID_INPUT):
    assert main(["api-generation", "generate", *args]) == code
    err = capsys.readouterr().err
    assert "Traceback" not in err and err.startswith("error: ")
    return err.splitlines()


@pytest.fixture
def validated_draft(tmp_path):
    env = _env()
    draft, validated = _draft(env)
    paths = []
    for name, value in (("validated.json", validated), ("draft.json", draft)):
        path = tmp_path / name
        path.write_text(json.dumps(asdict(value)))
        paths.append(path)
    return paths


def test_unreadable_draft_is_an_input_failure_with_cause_and_hint(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    lines = _fail(capsys, "--draft", str(bad), "--output-dir", str(tmp_path / "o"))

    assert lines[0].startswith("error: generation failed at stage 'input': InvalidDraftInputError: cannot read a draft from")
    assert any(line.startswith("  caused by: ") for line in lines)  # the underlying OSError is surfaced, not swallowed
    assert any("hint: pass a JSON file" in line and "examples/api-generation/draft.json" in line for line in lines)


def test_bad_config_file_is_reported_as_a_configuration_failure_not_input(tmp_path, validated_draft, capsys):
    config = tmp_path / "config.json"
    config.write_text("not json")

    lines = _fail(capsys, "--draft", str(validated_draft[0]), "--output-dir", str(tmp_path / "o"), "--config", str(config))

    assert lines[0].startswith("error: generation failed at stage 'configuration': ")
    assert any("hint: fix the option or the --config file" in line for line in lines)
    assert not (tmp_path / "o").exists()


def test_an_unvalidated_draft_fails_at_generation_with_an_actionable_hint(tmp_path, validated_draft, capsys):
    lines = _fail(capsys, "--draft", str(validated_draft[1]), "--output-dir", str(tmp_path / "o"))

    assert lines[0].startswith("error: generation failed at stage 'generation': DraftNotValidatedError")
    assert any("hint: the draft must be VALIDATED" in line for line in lines) and not (tmp_path / "o").exists()


def test_generated_artifact_validation_failure_lists_findings_and_writes_nothing(tmp_path, validated_draft, capsys, monkeypatch):
    real = FastAPIApplicationGenerator.generate
    monkeypatch.setattr(
        FastAPIApplicationGenerator, "generate",
        lambda self, draft: {**real(self, draft), "app/main.py": "def broken(:\n"},
    )

    lines = _fail(capsys, "--draft", str(validated_draft[0]), "--output-dir", str(tmp_path / "o"), code=EXIT_GENERATION_FAILED)

    assert lines[0].startswith("error: generation failed at stage 'validation': GeneratedArtifactRejectedError")
    assert any(line.startswith("  - SYNTAX_ERROR app/main.py") for line in lines)
    assert any("nothing was written" in line for line in lines) and not (tmp_path / "o").exists()


def test_output_conflict_keeps_its_own_label_and_hint(tmp_path, validated_draft, capsys):
    (tmp_path / "Dockerfile").write_text("mine")

    lines = _fail(capsys, "--draft", str(validated_draft[0]), "--output-dir", str(tmp_path))

    assert lines[0].startswith("error: output conflict at stage 'write': UnsafeOutputDirectoryError")
    assert any("hint: use an empty output directory" in line for line in lines)
