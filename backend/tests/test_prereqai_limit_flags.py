"""The analysis limit flags reject non-finite values as a usage error naming
the flag (exit 2) instead of a traceback, and a tiny positive file limit never
rounds down to an invalid 0 bytes."""
import json
from pathlib import Path

import pytest

from backend.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main


@pytest.mark.parametrize("flag", ["--max-seconds", "--max-file-mb"])
@pytest.mark.parametrize("value", ["nan", "inf", "abc"])
def test_invalid_limit_is_a_usage_error_naming_the_flag(flag, value, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["prerequisites", "analyze", "paper.pdf", flag, value])

    err = capsys.readouterr().err
    assert exit_info.value.code == EXIT_USAGE
    assert f"argument {flag}: '{value}' is not a finite number" in err
    assert "Traceback" not in err


def test_a_tiny_file_limit_still_means_at_least_one_byte():
    class _Platform:
        def analyze(self, paper, diagnostics, should_cancel, limits):
            self.limits = limits
            return {"status": "failure", "stage": "analysis", "detail": "x", "hint": None}

    from backend.cli_prerequisites import run_prerequisites_analyze
    from backend.cli import _build_parser

    platform = _Platform()
    args = _build_parser().parse_args(["prerequisites", "analyze", "p.pdf", "--max-file-mb", "1e-9"])
    run_prerequisites_analyze(args, platform=platform)

    assert platform.limits.max_file_bytes == 1


_SAMPLE = str(Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf")


@pytest.mark.parametrize("value", ["0", "-5"])
def test_a_non_positive_file_limit_is_reported_as_a_configuration_failure(value, capsys):
    assert main(["prerequisites", "analyze", _SAMPLE, "--max-file-mb", value, "--json"]) == EXIT_FAILURE
    outcome = json.loads(capsys.readouterr().out)

    assert outcome["status"] == "failure" and outcome["stage"] == "configuration"
    assert outcome["error"]["type"] == "InvalidConfigurationError" and "at least 1" in outcome["detail"]
    assert "session_id" not in outcome and "report" not in outcome  # nothing was analysed

    assert main(["prerequisites", "analyze", _SAMPLE, "--max-file-mb", value]) == EXIT_FAILURE
    err = capsys.readouterr().err
    assert "analysis failed at stage 'configuration'" in err and "hint: Limits must be positive numbers" in err


def test_valid_limits_still_analyse_the_sample_paper(capsys):
    assert main(["prerequisites", "analyze", _SAMPLE, "--max-file-mb", "20", "--max-seconds", "60", "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "success"
