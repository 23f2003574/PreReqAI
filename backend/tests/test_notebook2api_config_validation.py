"""Configuration the Notebook2API workflow consumes (CLI flags, an optional
--config file, the output directory) is validated first -- before the draft is
read or any generation work starts -- and every invalid field is reported."""
import json

import pytest

from backend.api_generation import APIGenerationConfig, InvalidProjectNameError
from backend.api_generation.config import config_file_text
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.llm.config import InvalidConfigurationError
from test_api_generation_cli import drafts  # noqa: F401  (fixture)


def test_defaults_and_valid_values_pass(tmp_path):
    assert APIGenerationConfig(str(tmp_path / "o")).validate().port == 8000
    assert APIGenerationConfig(str(tmp_path / "o"), "python:3.12-slim", 9000, "loan-quote").validate()


def test_missing_required_output_dir_is_reported():
    for missing in ("", "   ", None):
        with pytest.raises(InvalidConfigurationError, match="output_dir is required"):
            APIGenerationConfig(missing).validate()


@pytest.mark.parametrize(
    "bad,field",
    [({"port": 0}, "port"), ({"port": "80"}, "port"), ({"port": True}, "port"),
     ({"base_image": "Bad Image"}, "base_image"), ({"base_image": 3}, "base_image")],
)
def test_invalid_type_or_value_names_the_field(tmp_path, bad, field):
    with pytest.raises(InvalidConfigurationError, match=field):
        APIGenerationConfig(str(tmp_path / "o"), **bad).validate()


def test_a_single_invalid_project_name_keeps_its_specific_error(tmp_path):
    with pytest.raises(InvalidProjectNameError):
        APIGenerationConfig(str(tmp_path / "o"), project_name="1 bad").validate()


def test_several_invalid_fields_are_reported_together(tmp_path):
    target = tmp_path / "file"
    target.write_text("x")

    with pytest.raises(InvalidConfigurationError) as raised:
        APIGenerationConfig(str(target), "Bad Image", 0, "1 bad").validate()

    message = str(raised.value)
    assert all(token in message for token in ("output_dir", "base_image", "port", "project_name"))


def test_output_dir_that_is_an_existing_file_conflicts(tmp_path):
    target = tmp_path / "file"
    target.write_text("x")

    with pytest.raises(InvalidConfigurationError, match="existing file"):
        APIGenerationConfig(str(target)).validate()


def test_cli_validates_configuration_before_reading_the_draft(tmp_path, capsys):
    code = main(["api-generation", "generate", "--draft", str(tmp_path / "missing.json"),
                 "--output-dir", str(tmp_path / "o"), "--port", "0", "--base-image", "Bad Image"])

    err = capsys.readouterr().err
    assert code == EXIT_FAILURE and "stage 'configuration'" in err and "port" in err and "base_image" in err
    assert "cannot read a draft" not in err  # the draft was never touched


def test_a_valid_config_file_and_flag_override_still_generate(tmp_path, drafts, capsys):  # noqa: F811
    config = tmp_path / "prereqai-config.json"
    config.write_text(config_file_text("python:3.12-slim", 9000))

    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"),
                 "--config", str(config), "--port", "9100", "--json"])

    assert code == EXIT_OK and "PORT=9100" in (tmp_path / "o" / "Dockerfile").read_text()
    assert "python:3.12-slim" in (tmp_path / "o" / "Dockerfile").read_text()
    json.loads(capsys.readouterr().out)


def test_an_invalid_value_inside_a_config_file_is_caught_before_generation(tmp_path, drafts, capsys):  # noqa: F811
    config = tmp_path / "prereqai-config.json"
    config.write_text(json.dumps({**json.loads(config_file_text("python:3.12-slim", 9000)),
                                  "runtime": {"base_image": "python:3.12-slim", "port": 0}}))

    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"), "--config", str(config)])

    assert code == EXIT_FAILURE and "stage 'configuration'" in capsys.readouterr().err and not (tmp_path / "o").exists()
