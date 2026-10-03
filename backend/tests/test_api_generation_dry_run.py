import json

import pytest

from backend.api_generation import (
    APIGenerationConfig,
    UnsafeOutputDirectoryError,
    generate_application,
    generation_status,
)
from backend.cli import EXIT_INVALID_INPUT, EXIT_OK, main
from backend.llm.config import InvalidConfigurationError
from test_api_generation_boundary import _draft, _env
from test_api_generation_cli import drafts  # noqa: F401  (fixture)


def _setup():
    env = _env()
    _, validated = _draft(env)
    return env["draft"], validated


def test_dry_run_reports_the_same_files_and_location_as_a_real_run_but_writes_nothing(tmp_path):
    service, draft = _setup()
    out = tmp_path / "out"

    planned = generate_application(service, draft, out, dry_run=True)

    assert planned.dry_run and not out.exists()
    real = generate_application(service, draft, out)
    assert not real.dry_run and planned.files == real.files and planned.output_dir == real.output_dir
    assert planned.openapi_path == real.openapi_path


def test_dry_run_leaves_an_existing_directory_untouched(tmp_path):
    service, draft = _setup()
    out = tmp_path / "out"
    first = generate_application(service, draft, out)
    snapshot = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    (out / "app" / "main.py").write_text("hand edit")
    snapshot[out / "app" / "main.py"] = b"hand edit"

    generate_application(service, draft, out, dry_run=True)

    assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == snapshot
    assert generation_status(out) == "complete" and first.files


def test_dry_run_reports_an_output_conflict_exactly_like_a_real_run(tmp_path):
    service, draft = _setup()
    (tmp_path / "Dockerfile").write_text("mine")

    with pytest.raises(UnsafeOutputDirectoryError) as dry:
        generate_application(service, draft, tmp_path, dry_run=True)
    with pytest.raises(UnsafeOutputDirectoryError) as real:
        generate_application(service, draft, tmp_path)

    assert dry.value.stage == real.value.stage == "write" and str(dry.value) == str(real.value)
    assert (tmp_path / "Dockerfile").read_text() == "mine" and not (tmp_path / "app").exists()


def test_dry_run_fails_on_invalid_configuration_the_same_way(tmp_path):
    service, draft = _setup()
    for dry_run in (True, False):
        with pytest.raises(InvalidConfigurationError) as raised:
            generate_application(service, draft, config=APIGenerationConfig(str(tmp_path / "o"), port=0), dry_run=dry_run)
        assert raised.value.stage == "configuration"
    assert not (tmp_path / "o").exists()


def test_output_path_that_is_a_file_is_a_conflict_in_both_modes(tmp_path):
    service, draft = _setup()
    target = tmp_path / "file"
    target.write_text("x")

    for dry_run in (True, False):
        with pytest.raises(UnsafeOutputDirectoryError):
            generate_application(service, draft, target, dry_run=dry_run)


def test_cli_dry_run_reports_and_writes_nothing(tmp_path, drafts, capsys):  # noqa: F811
    out = tmp_path / "project"

    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(out), "--dry-run"])

    text = capsys.readouterr().out
    assert code == EXIT_OK and "Dry run: would generate POST /add" in text and "no files were written" in text
    assert not out.exists()

    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(out), "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK and payload["dry_run"] is True and "app/main.py" in payload["files"] and not out.exists()


def test_cli_distinguishes_invalid_input_from_an_existing_output_conflict_and_real_runs_are_unchanged(tmp_path, drafts, capsys):  # noqa: F811
    (tmp_path / "Dockerfile").write_text("mine")
    conflict = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path), "--dry-run"])
    conflict_err = capsys.readouterr().err
    invalid = main(["api-generation", "generate", "--draft", str(drafts[1]), "--output-dir", str(tmp_path / "x"), "--dry-run"])
    invalid_err = capsys.readouterr().err

    assert conflict == invalid == EXIT_INVALID_INPUT
    assert "output conflict at stage 'write'" in conflict_err and "generation failed at stage 'generation'" in invalid_err

    real = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "ok")])
    assert real == EXIT_OK and (tmp_path / "ok" / "app" / "main.py").is_file() and "Generated POST /add" in capsys.readouterr().out
