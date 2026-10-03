"""Each CLI domain has one home and each api-generation command reaches its one
workflow: `generate` -> generate_application, `check` -> check_generated_project.
The public names stay importable from backend.cli."""
import ast
from pathlib import Path

import backend.cli as cli
import backend.cli_api_generation as generation_cli
from backend import cli_common
from backend.cli import EXIT_OK, main

BACKEND = Path(cli.__file__).parent
EXAMPLE_DRAFT = BACKEND.parent / "examples" / "api-generation" / "draft.json"


def _imported_modules(path):
    tree = ast.parse(path.read_text())
    return {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}


def test_generate_reaches_the_generation_workflow_and_not_the_health_check(tmp_path, monkeypatch, capsys):
    calls = []
    real_generate, real_check = generation_cli.generate_application, generation_cli.check_generated_project
    monkeypatch.setattr(generation_cli, "generate_application", lambda *a, **k: calls.append("generate") or real_generate(*a, **k))
    monkeypatch.setattr(generation_cli, "check_generated_project", lambda *a, **k: calls.append("check") or real_check(*a, **k))

    code = main(["api-generation", "generate", "--draft", str(EXAMPLE_DRAFT), "--output-dir", str(tmp_path / "o"), "-q"])

    assert code == EXIT_OK and calls == ["generate"] and (tmp_path / "o" / "README.md").is_file()
    capsys.readouterr()


def test_check_reaches_the_health_check_and_never_generates(tmp_path, monkeypatch, capsys):
    main(["api-generation", "generate", "--draft", str(EXAMPLE_DRAFT), "--output-dir", str(tmp_path / "o"), "-q"])
    capsys.readouterr()
    calls = []
    real_generate, real_check = generation_cli.generate_application, generation_cli.check_generated_project
    monkeypatch.setattr(generation_cli, "generate_application", lambda *a, **k: calls.append("generate") or real_generate(*a, **k))
    monkeypatch.setattr(generation_cli, "check_generated_project", lambda *a, **k: calls.append("check") or real_check(*a, **k))
    before = sorted(p.name for p in (tmp_path / "o").rglob("*") if "__pycache__" not in p.parts)

    code = main(["api-generation", "check", str(tmp_path / "o")])

    assert code == EXIT_OK and calls == ["check"]
    assert sorted(p.name for p in (tmp_path / "o").rglob("*") if "__pycache__" not in p.parts) == before
    capsys.readouterr()


def test_the_two_cli_domains_do_not_import_each_other_s_workflows():
    recovery = "backend.agent_task_recovery_execution_precondition_snapshots"
    generation = _imported_modules(BACKEND / "cli_api_generation.py")
    main_cli = _imported_modules(BACKEND / "cli.py")

    assert recovery not in generation and not any(m.startswith("backend.cli") and m != "backend.cli_common" for m in generation)
    assert "backend.api_generation" not in main_cli and "backend.api_documentation_draft" not in main_cli


def test_public_names_remain_importable_from_backend_cli_and_share_one_definition():
    for name in ("main", "EXIT_OK", "EXIT_FAILURE", "EXIT_USAGE", "EXIT_INVALID_INPUT", "EXIT_GENERATION_FAILED",
                 "EXIT_INTERNAL_ERROR", "_generation_exit_code", "_load_draft", "_build_parser", "build_recovery_decision_facade"):
        assert hasattr(cli, name), name
    assert cli._generation_exit_code is generation_cli._generation_exit_code
    assert (cli.EXIT_OK, cli.EXIT_FAILURE, cli.EXIT_USAGE) == (cli_common.EXIT_OK, cli_common.EXIT_FAILURE, cli_common.EXIT_USAGE) == (0, 1, 2)
