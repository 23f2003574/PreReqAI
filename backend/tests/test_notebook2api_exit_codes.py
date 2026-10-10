"""The exit-code contract of `api-generation generate`: one centralized mapping
from existing errors to 0 / 2 / 3 / 4 / 5, valid --json output on every failure."""
import json

import pytest

import backend.api_generation.writer as writer
from backend.api_generation import (
    DraftNotValidatedError,
    FastAPIApplicationGenerator,
    InvalidDraftInputError,
    UnsafeOutputDirectoryError,
)
from backend.cli import (
    EXIT_GENERATION_FAILED,
    EXIT_INTERNAL_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_OK,
    EXIT_USAGE,
    _generation_exit_code,
    main,
)
from test_api_generation_cli import drafts  # noqa: F401  (fixture)


def _generate(capsys, *args):
    code = main(["api-generation", "generate", *args, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_codes_are_distinct_and_success_is_zero(tmp_path, drafts, capsys):  # noqa: F811
    assert len({EXIT_OK, EXIT_USAGE, EXIT_INVALID_INPUT, EXIT_GENERATION_FAILED, EXIT_INTERNAL_ERROR}) == 5
    code, data = _generate(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"))
    assert (code, data["status"]) == (EXIT_OK, "success")


def test_usage_errors_exit_2(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["api-generation", "generate", "--output-dir", "x"])
    assert raised.value.code == EXIT_USAGE
    capsys.readouterr()


def test_invalid_input_configuration_and_target_all_exit_3_with_valid_json(tmp_path, drafts, capsys):  # noqa: F811
    (tmp_path / "Dockerfile").write_text("mine")
    cases = {
        "bad draft file": ["--draft", str(tmp_path / "missing.json"), "--output-dir", str(tmp_path / "a")],
        "bad configuration": ["--draft", str(drafts[0]), "--output-dir", str(tmp_path / "b"), "--port", "0"],
        "unvalidated draft": ["--draft", str(drafts[1]), "--output-dir", str(tmp_path / "c")],
        "output conflict": ["--draft", str(drafts[0]), "--output-dir", str(tmp_path)],
    }
    for name, args in cases.items():
        code, data = _generate(capsys, *args)
        assert code == EXIT_INVALID_INPUT and data["status"] == "failed", name


def test_validation_rejection_and_write_failure_exit_4(tmp_path, drafts, capsys, monkeypatch):  # noqa: F811
    real = FastAPIApplicationGenerator.generate
    monkeypatch.setattr(FastAPIApplicationGenerator, "generate", lambda self, d: {**real(self, d), "app/main.py": "def broken(:\n"})
    code, data = _generate(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "a"))
    assert code == EXIT_GENERATION_FAILED and data["failed_stage"] == "validation"
    monkeypatch.undo()

    def disk_full(target, text):
        raise OSError("disk full")

    monkeypatch.setattr(writer, "_atomic_write", disk_full)
    code, data = _generate(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "b"))
    assert code == EXIT_GENERATION_FAILED and data["failed_stage"] == "write"


def test_an_unexpected_exception_is_a_distinct_internal_error_not_disguised_as_input(tmp_path, drafts, capsys, monkeypatch):  # noqa: F811
    def bug(self, draft):
        raise RuntimeError("bug in the generator")

    monkeypatch.setattr(FastAPIApplicationGenerator, "generate", bug)

    code, data = _generate(capsys, "--draft", str(drafts[0]), "--output-dir", str(tmp_path / "o"))

    assert code == EXIT_INTERNAL_ERROR and data["error"]["type"] == "RuntimeError" and data["failed_stage"] == "generation"
    assert not (tmp_path / "o").exists()


def test_the_mapping_is_one_function_over_the_existing_error_types():
    assert _generation_exit_code(InvalidDraftInputError("x")) == EXIT_INVALID_INPUT
    assert _generation_exit_code(UnsafeOutputDirectoryError("x")) == EXIT_INVALID_INPUT
    assert _generation_exit_code(DraftNotValidatedError("x")) == EXIT_INVALID_INPUT
    assert _generation_exit_code(ValueError("a plain ValueError is not user input")) == EXIT_INTERNAL_ERROR
    assert _generation_exit_code(OSError("outside the write stage")) == EXIT_INTERNAL_ERROR
