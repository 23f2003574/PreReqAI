"""The CLI's --help is accurate: it names the real commands and options, its
example runs, the documented JSON keys and exit codes match behavior."""
import json
import re
import shlex
from pathlib import Path

import pytest

from backend.cli import (
    EXIT_GENERATION_FAILED,
    EXIT_INTERNAL_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_OK,
    EXIT_USAGE,
    _build_parser,
    main,
)

ROOT = Path(__file__).resolve().parents[2]


def _help(capsys, *args):
    with pytest.raises(SystemExit) as raised:
        main([*args, "--help"])
    assert raised.value.code == 0
    return capsys.readouterr().out


def test_top_level_and_group_help_describe_the_supported_workflow(capsys):
    top = " ".join(_help(capsys).split())
    group = " ".join(_help(capsys, "api-generation").split())

    assert "api-generation" in top and "validated API documentation draft" in top
    assert "generate" in group and "check" in group and "examples/api-generation/" in group


def test_generate_help_lists_every_option_the_parser_defines(capsys):
    text = _help(capsys, "api-generation", "generate")
    generate = next(a for a in _build_parser()._subparsers._group_actions[0].choices["api-generation"]._subparsers._group_actions[0].choices.items() if a[0] == "generate")[1]
    options = {o for action in generate._actions for o in action.option_strings if o.startswith("--")}

    assert options >= {"--draft", "--output-dir", "--base-image", "--port", "--config", "--project-name", "--dry-run", "--json", "--help"}
    assert all(option in text for option in options)
    assert "VALIDATED" in text and "Stages:" in text and "overrides --config" in text


def test_the_documented_example_uses_real_files_and_actually_runs(tmp_path, capsys):
    text = _help(capsys, "api-generation", "generate")
    example_section = text.split("Example:", 1)[1]  # the usage line also starts with `python -m backend.cli`
    example = re.search(r"python -m backend\.cli (api-generation generate .*?)\s+#", example_section, flags=re.DOTALL).group(1)
    args = shlex.split(example.replace("\\\n", " "))
    assert (ROOT / args[args.index("--draft") + 1]).is_file()
    args[args.index("--output-dir") + 1] = str(tmp_path / "out")

    assert main([*args, "--json"]) == EXIT_OK  # --dry-run in the example: a real, successful run
    assert not (tmp_path / "out").exists()
    capsys.readouterr()


def test_documented_json_keys_exist_in_real_success_and_failure_output(tmp_path, capsys):
    text = " ".join(_help(capsys, "api-generation", "generate").split())
    draft = ROOT / "examples" / "api-generation" / "draft.json"
    main(["api-generation", "generate", "--draft", str(draft), "--output-dir", str(tmp_path / "o"), "--dry-run", "--json"])
    ok = json.loads(capsys.readouterr().out)
    main(["api-generation", "generate", "--draft", str(tmp_path / "x.json"), "--output-dir", str(tmp_path / "o"), "--json"])
    failed = json.loads(capsys.readouterr().out)

    documented = ["status", "source", "stages_completed", "validation", "warnings", "dry_run", "draft_id", "endpoint",
                  "output_dir", "files", "openapi_path", "artifact_types", "failed_stage", "error"]
    assert all(key in text for key in documented)
    assert set(documented) <= set(ok) | set(failed)


def test_documented_exit_codes_match_the_constants(capsys):
    text = " ".join(_help(capsys, "api-generation", "generate").split())

    for code, phrase in ((EXIT_OK, "0 success"), (EXIT_USAGE, "2 usage error"), (EXIT_INVALID_INPUT, "3 invalid input"),
                         (EXIT_GENERATION_FAILED, "4 generation, validation or write failed"), (EXIT_INTERNAL_ERROR, "5 unexpected internal error")):
        assert phrase in text and phrase.startswith(str(code))


def test_check_help_describes_what_it_checks_and_its_exit_codes(capsys):
    text = " ".join(_help(capsys, "api-generation", "check").split())

    assert "project_dir" in text and "--json" in text and "Exit codes: 0 healthy; 1 invalid or incompatible; 2 usage error." in text
    assert "compatibility" in text


def test_top_level_help_says_how_to_run_lists_the_main_command_first_and_its_examples_parse(capsys):
    from backend.cli import _build_parser

    text = _help(capsys)
    assert "python -m backend.cli <command>" in text
    commands = text.split("<command>\n", 1)[1]
    assert commands.index("prerequisites") < commands.index("api-generation") < commands.index("recovery-decision")

    examples = [line.strip().replace("\\", "") for line in text.split("Examples:", 1)[1].split("\n\n", 1)[0].splitlines()]
    joined = " ".join(examples).split("python -m backend.cli ")[1:]
    assert len(joined) == 3
    for example in joined:
        _build_parser().parse_args(example.split())  # every example is a valid invocation


def test_every_subcommand_documents_its_exit_codes(capsys):
    for args in (("prerequisites", "analyze"), ("api-generation", "generate"), ("api-generation", "check"),
                 ("recovery-decision", "evaluate"), ("recovery-decision", "diagnose"), ("recovery-decision", "readiness")):
        text = " ".join(_help(capsys, *args).split())
        assert "Exit codes: 0 " in text and "2 usage error" in text, args


def test_usage_and_error_lines_name_the_real_invocation_not_an_uninstalled_script(capsys):
    assert _help(capsys).startswith("usage: python -m backend.cli [-h] [--version] <command>")
    assert _help(capsys, "prerequisites", "analyze").startswith("usage: python -m backend.cli prerequisites analyze")
    with pytest.raises(SystemExit) as raised:
        main(["prerequisites"])
    err = capsys.readouterr().err
    assert raised.value.code == EXIT_USAGE and "python -m backend.cli prerequisites: error:" in err
    assert "prereqai " not in err  # no `prereqai` console script is installed anywhere
