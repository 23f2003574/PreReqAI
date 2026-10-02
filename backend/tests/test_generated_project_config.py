"""prereqai-config.json: the generated project's one editable settings file.
It holds exactly the generation settings the generator consumes (base image,
port, project name), is validated by APIGenerationConfig.validate(), feeds
back into `generate --config`, and must agree with the rest of the project."""
import json
from pathlib import Path

import pytest

from backend.api_generation import CONFIG_FILENAME, APIGenerationConfig, check_generated_project, validate_generated_artifact
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.llm.config import InvalidConfigurationError
from test_generated_project_clean_build import _clean_copy
from test_generated_project_importability import EXAMPLE, _probe

DRAFT = str(EXAMPLE / "draft.json")


def _generate(out, capsys, *extra):
    code = main(["api-generation", "generate", "--draft", DRAFT, "--output-dir", str(out), *extra])
    captured = capsys.readouterr()
    return code, captured.err


def _config(project: Path) -> dict:
    return json.loads((project / CONFIG_FILENAME).read_text())


def test_default_configuration_is_explicit_and_deterministic(tmp_path, capsys):
    assert _generate(tmp_path / "a", capsys)[0] == EXIT_OK
    assert _generate(tmp_path / "b", capsys)[0] == EXIT_OK

    text = (tmp_path / "a" / CONFIG_FILENAME).read_text()
    assert json.loads(text) == {"config_version": 1, "generation": {"project_name": None}, "runtime": {"base_image": "python:3.11-slim", "port": 8000}}
    assert text == (tmp_path / "b" / CONFIG_FILENAME).read_text()
    assert "/tmp" not in text and str(tmp_path) not in text  # no output_dir or other machine paths
    manifest = json.loads((tmp_path / "a" / "prereqai-manifest.json").read_text())
    assert {"path": CONFIG_FILENAME, "type": "project-configuration"} in manifest["artifacts"]
    assert f"`{CONFIG_FILENAME}`" in (tmp_path / "a" / "README.md").read_text()


def test_customized_configuration_drives_the_project_and_round_trips(tmp_path, capsys):
    first = tmp_path / "first"
    assert _generate(first, capsys, "--port", "9100", "--base-image", "python:3.12-slim",
                     "--project-name", "loan-quote")[0] == EXIT_OK
    assert _config(first) == {"config_version": 1, "generation": {"project_name": "loan-quote"}, "runtime": {"base_image": "python:3.12-slim", "port": 9100}}

    # a hand-edited copy regenerates the project; explicit flags still win
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps({**_config(first), "runtime": {**_config(first)["runtime"], "port": 9200}}))
    second = tmp_path / "second"
    assert _generate(second, capsys, "--config", str(edited), "--base-image", "python:3.13-slim")[0] == EXIT_OK

    assert _config(second) == {"config_version": 1, "generation": {"project_name": "loan-quote"}, "runtime": {"base_image": "python:3.13-slim", "port": 9200}}
    dockerfile = (second / "Dockerfile").read_text()
    assert dockerfile.startswith("FROM python:3.13-slim\n") and "PORT=9200" in dockerfile
    assert (second / "loan_quote" / "main.py").is_file()
    assert check_generated_project(second).healthy


@pytest.mark.parametrize("section, change, message", [
    ("runtime", {"port": 0}, "port 0 must be an integer from 1 to 65535"),
    ("runtime", {"port": "8000"}, "port '8000' must be an integer"),
    ("runtime", {"port": True}, "port True must be an integer"),
    ("runtime", {"base_image": "Not An Image"}, "is not a valid image reference"),
    ("generation", {"project_name": "my api"}, "must start with a letter"),
    ("generation", {"project_name": 7}, "must be a string or null"),
    (None, {"config_version": 2}, "unsupported config_version 2"),
    ("runtime", {"prot": 8000}, "section 'runtime' must contain exactly"),
    (None, {"port": 8000}, "must contain exactly"),
    (None, {"runtime": {"port": 8000}}, "section 'runtime' must contain exactly"),
])
def test_invalid_configuration_fails_clearly_before_anything_is_written(tmp_path, capsys, section, change, message):
    data = {"config_version": 1, "generation": {"project_name": None},
            "runtime": {"base_image": "python:3.11-slim", "port": 8000}}
    if section is None:
        data.update(change)
    else:
        data[section] = {**data[section], **change}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))
    out = tmp_path / "project"

    code, err = _generate(out, capsys, "--config", str(config_file))

    assert code == EXIT_FAILURE and ("InvalidConfigurationError" in err or "InvalidProjectNameError" in err)
    assert message in err and not out.exists()


def test_missing_settings_and_bad_files_never_fall_back_to_defaults(tmp_path):
    for text in ('{"config_version": 1, "runtime": {"base_image": "python:3.11-slim", "port": 8000}}',
                 '{"config_version": 1, "generation": {}, "runtime": {"base_image": "python:3.11-slim", "port": 8000}}',
                 "not json", "[]"):
        with pytest.raises(InvalidConfigurationError):
            APIGenerationConfig.from_file_text(text, str(tmp_path))
    with pytest.raises(InvalidConfigurationError, match="cannot read"):
        APIGenerationConfig.from_file(tmp_path / "absent.json", str(tmp_path))


def test_a_configuration_that_disagrees_with_the_project_is_reported(tmp_path, capsys):
    project = tmp_path / "project"
    assert _generate(project, capsys)[0] == EXIT_OK
    (project / CONFIG_FILENAME).write_text(json.dumps({**_config(project), "runtime": {"base_image": "python:3.11-slim", "port": 9999}}))

    health = check_generated_project(project)
    assert not health.healthy and health.checks["manifest"] == "failed"
    assert {f["category"] for f in health.findings} == {"CONFIG_MISMATCH"}

    (project / CONFIG_FILENAME).write_text("{}")
    assert "INVALID_CONFIG" in {f["category"] for f in check_generated_project(project).findings}


def test_clean_output_loads_its_configuration_without_host_internals(tmp_path, capsys):
    project = tmp_path / "project"
    assert _generate(project, capsys, "--project-name", "loan-quote", "--port", "9100")[0] == EXIT_OK
    clean = _clean_copy(project, tmp_path / "clean")

    assert (clean / CONFIG_FILENAME).is_file()  # declared in the manifest, so part of the clean project
    assert check_generated_project(clean).healthy
    seen = _probe(clean, "loan_quote")
    assert seen["blocked"] == [] and seen["host_modules"] == []
    # plain JSON, read with the standard library alone, and usable as --config input
    assert json.loads((clean / CONFIG_FILENAME).read_text())["runtime"]["port"] == 9100
    again = tmp_path / "again"
    assert _generate(again, capsys, "--config", str(clean / CONFIG_FILENAME))[0] == EXIT_OK
    assert (again / CONFIG_FILENAME).read_bytes() == (clean / CONFIG_FILENAME).read_bytes()
    assert validate_generated_artifact({p.relative_to(again).as_posix(): p.read_text()
                                        for p in again.rglob("*") if p.is_file() and p.name != ".prereqai-generated.json"}).valid
