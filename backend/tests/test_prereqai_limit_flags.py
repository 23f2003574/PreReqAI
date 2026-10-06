"""The analysis limit flags reject non-finite values as a usage error naming
the flag (exit 2) instead of a traceback, and a tiny positive file limit never
rounds down to an invalid 0 bytes."""
import pytest

from backend.cli import EXIT_USAGE, main


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
