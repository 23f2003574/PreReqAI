import pytest

from backend.api_generation import APIGenerationConfig, FastAPIApplicationGenerator, generate_application
from backend.cli import EXIT_INVALID_INPUT, EXIT_OK, main
from backend.llm.config import InvalidConfigurationError
from test_api_generation_boundary import _draft, _env
from test_api_generation_cli import drafts  # noqa: F401  (fixture)


def _run(tmp_path, **config):
    env = _env()
    _, validated = _draft(env)
    out = tmp_path / "out"
    return generate_application(env["draft"], validated, config=APIGenerationConfig(str(out), **config)), out


def test_defaults_reproduce_the_previous_output_exactly(tmp_path):
    _, out = _run(tmp_path)
    env = _env()
    _, validated = _draft(env)
    expected = FastAPIApplicationGenerator().generate(validated)

    assert {p: (out / p).read_text() for p in expected} == expected
    dockerfile = (out / "Dockerfile").read_text()
    assert "FROM python:3.11-slim" in dockerfile and "PORT=8000" in dockerfile and "EXPOSE 8000" in dockerfile


def test_explicit_configuration_reaches_the_generated_dockerfile(tmp_path):
    _, out = _run(tmp_path, base_image="python:3.12-slim", port=9000)

    dockerfile = (out / "Dockerfile").read_text()
    assert "FROM python:3.12-slim" in dockerfile and "PORT=9000" in dockerfile and "EXPOSE 9000" in dockerfile


@pytest.mark.parametrize(
    "bad",
    [
        {"output_dir": ""},
        {"base_image": "python:3.11\nRUN evil"},
        {"base_image": "UPPER case"},
        {"port": 0},
        {"port": 70000},
        {"port": "8000"},
        {"port": True},
    ],
)
def test_invalid_configuration_is_rejected_with_the_existing_error_type(tmp_path, bad):
    config = APIGenerationConfig(**{"output_dir": str(tmp_path / "o"), **bad})

    with pytest.raises(InvalidConfigurationError):
        config.validate()


def test_invalid_configuration_stops_generation_before_anything_is_written(tmp_path):
    env = _env()
    _, validated = _draft(env)
    out = tmp_path / "out"

    with pytest.raises(InvalidConfigurationError) as raised:
        generate_application(env["draft"], validated, config=APIGenerationConfig(str(out), port=0))
    assert raised.value.stage == "configuration" and not out.exists()


def test_output_dir_cannot_be_given_twice_or_be_an_existing_file(tmp_path):
    env = _env()
    _, validated = _draft(env)
    target = tmp_path / "f"
    target.write_text("x")

    with pytest.raises(InvalidConfigurationError):
        APIGenerationConfig(str(target)).validate()
    with pytest.raises(ValueError) as raised:
        generate_application(env["draft"], validated, tmp_path / "a", config=APIGenerationConfig(str(tmp_path / "b")))
    assert raised.value.stage == "configuration"


def test_cli_flags_override_defaults_and_bad_values_fail_cleanly(tmp_path, drafts, capsys):
    ok = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "p"),
               "--base-image", "python:3.12-slim", "--port", "9100"])
    assert ok == EXIT_OK and "PORT=9100" in (tmp_path / "p" / "Dockerfile").read_text()
    capsys.readouterr()

    bad = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "q"), "--port", "0"])
    err = capsys.readouterr().err
    assert bad == EXIT_INVALID_INPUT and "stage 'configuration'" in err and "InvalidConfigurationError" in err
    assert not (tmp_path / "q").exists()
