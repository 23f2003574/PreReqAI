"""The supported Notebook2API entrypoint (`api-generation generate`, run on the
committed example draft) reaches the whole current generation pipeline, in
order, and the lower-level APIs other callers use are still exported."""
import json
from pathlib import Path

import backend.api_generation as api_generation
import backend.api_generation.workflow as workflow
from backend.api_generation import FastAPIApplicationGenerator, LLMAPIGenerationService
from backend.cli import EXIT_OK, main

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "api-generation" / "draft.json"


def test_cli_entrypoint_reaches_boundary_generator_validation_and_writer_in_order(tmp_path, monkeypatch, capsys):
    calls = []

    def spy(owner, name, label):
        real = getattr(owner, name)

        def wrapper(*args, **kwargs):
            calls.append(label)
            return real(*args, **kwargs)

        monkeypatch.setattr(owner, name, wrapper)

    spy(LLMAPIGenerationService, "generate", "boundary")
    spy(FastAPIApplicationGenerator, "generate", "generator")
    spy(workflow, "require_valid", "validation")
    spy(workflow, "write_generated_application", "write")
    out = tmp_path / "project"

    code = main(["api-generation", "generate", "--draft", str(EXAMPLE), "--output-dir", str(out), "--json"])

    result = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK and calls == ["boundary", "generator", "validation", "write"]
    assert result["endpoint"] == "POST /loan-quote" and result["dry_run"] is False
    assert all((out / path).is_file() for path in result["files"])
    assert main(["api-generation", "check", str(out)]) == EXIT_OK  # the same entrypoint family verifies it


def test_lower_level_apis_remain_exported():
    for name in (
        "generate_application", "LLMAPIGenerationService", "FastAPIApplicationGenerator", "validate_generated_artifact",
        "require_valid", "write_generated_application", "write_openapi_contract", "run_release_checklist",
        "check_generated_project", "APIGenerationConfig",
    ):
        assert hasattr(api_generation, name) and name in api_generation.__all__
