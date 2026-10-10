"""Release configuration: the Docker base image written into a generated
project's Dockerfile must be a reference `docker build` accepts. Malformed
references fail validation through the existing InvalidConfigurationError
(CLI exit 3 at the configuration stage) instead of producing a project that
reports success but cannot be built."""
from pathlib import Path

import pytest

from backend.api_generation import APIGenerationConfig
from backend.cli import main
from backend.cli_api_generation import EXIT_INVALID_INPUT
from backend.llm.config import InvalidConfigurationError

DRAFT = Path(__file__).resolve().parents[2] / "examples" / "api-generation" / "draft.json"
VALID = ["python:3.11-slim", "python", "library/python:3.12", "ghcr.io/org/team/api-base:1.0",
         "localhost:5000/python:3.11-slim", "registry.example.com:443/py_base__x:v1.2.3",
         "python@sha256:" + "a" * 64, "python:3.11-slim@sha256:" + "0" * 64]
INVALID = ["python/", "/python", "python//slim", "a..b", "python.:3", "-python", "Python:3.11", "python:",
           "python:-tag", "python:3.11 slim", "python@sha256:abc", ""]


@pytest.mark.parametrize("image", VALID)
def test_valid_image_references_are_accepted(tmp_path, image):
    assert APIGenerationConfig(output_dir=str(tmp_path / "o"), base_image=image).validate().base_image == image


@pytest.mark.parametrize("image", INVALID)
def test_malformed_image_references_are_rejected(tmp_path, image):
    with pytest.raises(InvalidConfigurationError, match="is not a valid image reference"):
        APIGenerationConfig(output_dir=str(tmp_path / "o"), base_image=image).validate()


def test_cli_stops_at_configuration_and_writes_nothing_for_a_malformed_image(tmp_path, capsys):
    code = main(["api-generation", "generate", "--draft", str(DRAFT),
                 "--output-dir", str(tmp_path / "o"), "--base-image", "python//slim", "-q"])

    err = capsys.readouterr().err
    assert code == EXIT_INVALID_INPUT and "stage 'configuration'" in err and "python//slim" in err
    assert not (tmp_path / "o").exists()
