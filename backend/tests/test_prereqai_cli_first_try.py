"""A first try with no command shows the help (with "start here" and examples) on stderr and exits 2, instead of a bare argparse error."""
from backend.cli import main


def test_no_command_shows_help_pointing_at_the_first_command(capsys):
    assert main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "(start here)" in captured.err
    assert "prerequisites analyze paper.pdf" in captured.err
    assert "error:" not in captured.err


def test_a_real_usage_error_is_still_reported_as_an_error(capsys):
    try:
        main(["prerequisites"])
    except SystemExit as exit_:
        assert exit_.code == 2
    assert "python -m backend.cli prerequisites: error:" in capsys.readouterr().err
