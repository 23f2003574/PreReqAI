"""Release smoke test for the generated-project lifecycle, end to end through
the real orchestration and CLI:

notebook fixture -> validated API draft -> `api-generation generate` ->
metadata + manifest -> generated application -> configuration/dependencies
-> OpenAPI -> artifact validation -> health (`check`) and release checklist
-> compatibility diagnostics (current, upgradable, unsupported) -> safe
regeneration into the same location."""
import json
import shlex
import subprocess
import sys
from dataclasses import asdict

from backend.api_generation import check_generated_project, run_release_checklist
from backend.api_generation import metadata as metadata_module
from backend.cli import EXIT_INVALID_INPUT, EXIT_OK, main, EXIT_FAILURE
from test_api_generation_boundary import _draft, _env
from test_generated_project_clean_build import _clean_copy
from test_generated_project_importability import _PROBE, REPO_ROOT


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def _cli(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _set_contract(project, version):
    for name in ("prereqai-project.json", "prereqai-manifest.json"):
        data = json.loads((project / name).read_text())
        data["contract_version"] = version
        (project / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_generated_project_release_lifecycle(tmp_path, capsys, monkeypatch):
    # notebook fixture -> validated draft (the scripted LLM pipeline the suite already uses)
    env = _env()
    _, validated = _draft(env)
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps(asdict(validated)))
    project = tmp_path / "add-service"
    generate = ["api-generation", "generate", "--draft", str(draft_file), "--output-dir", str(project),
                "--project-name", "add-service", "--port", "9100"]

    # generation through the CLI (a dry run first changes nothing)
    code, out, _ = _cli(capsys, *generate, "--dry-run", "--json")
    assert code == EXIT_OK and json.loads(out)["dry_run"] and not project.exists()
    code, out, err = _cli(capsys, *generate, "--json")
    assert code == EXIT_OK, err
    result = json.loads(out)
    assert result["endpoint"] == "POST /add"
    assert {"add_service/__init__.py", "add_service/main.py", "requirements.txt", "Dockerfile", "README.md",
            "openapi.json", "prereqai-project.json", "prereqai-manifest.json", "prereqai-config.json"} == set(result["files"])

    # metadata + manifest + configuration + dependencies agree on one identity
    metadata = json.loads((project / "prereqai-project.json").read_text())
    manifest = json.loads((project / "prereqai-manifest.json").read_text())
    config = json.loads((project / "prereqai-config.json").read_text())
    assert (metadata["draft_id"], metadata["endpoint"], metadata["project_name"]) == (validated.draft_id, "POST /add", "add-service")
    assert manifest["application"] == {"name": "add-service", "entrypoint": "add_service.main:app"}
    assert sorted(a["path"] for a in manifest["artifacts"]) == sorted(set(result["files"]) - {"prereqai-manifest.json"})
    assert config == {"config_version": 1, "generation": {"project_name": "add-service"},
                      "runtime": {"base_image": "python:3.11-slim", "port": 9100}}
    assert (project / "requirements.txt").read_text().splitlines() == ["fastapi>=0.115.0", "pydantic>=2.0", "uvicorn>=0.32.0"]
    assert "COPY add_service ./add_service" in (project / "Dockerfile").read_text()

    # generated application: imports standalone from a clean copy, serves its example, matches openapi.json
    clean = _clean_copy(project, tmp_path / "clean")
    example = validated.examples[0]
    probe = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE, str(clean), "add_service", str(REPO_ROOT), json.dumps(example["input"])],
        cwd=clean, capture_output=True, text=True, timeout=60,
    )
    assert probe.returncode == 0, probe.stderr
    seen = json.loads(probe.stdout)
    assert seen["status"] == 200 and seen["result"] == example["output"]
    assert seen["blocked"] == [] and seen["host_modules"] == []
    assert seen["openapi_paths"] == ["/add"] == sorted(json.loads((project / "openapi.json").read_text())["paths"])

    # artifact validation + health + release checklist: healthy, ready, current, no upgrade signal
    code, out, _ = _cli(capsys, "api-generation", "check", str(project), "--json")
    health = json.loads(out)
    assert code == EXIT_OK and health["status"] == "healthy" and health["findings"] == []
    assert health["compatibility"]["status"] == "compatible"
    assert health["compatibility"]["remediation"] is None and health["compatibility"]["regeneration"] is None
    assert check_generated_project(clean).healthy
    checklist = run_release_checklist(env["draft"], validated)
    assert checklist.ready and checklist.failures == []
    assert checklist.compatibility["status"] == "compatible"
    assert not any(w.startswith("compatibility") for w in checklist.warnings)

    # a deliberately newer contract: incompatible, stronger error, no regeneration advice
    generated_tree = _tree(project)
    _set_contract(project, 2)
    code, out, _ = _cli(capsys, "api-generation", "check", str(project))
    assert code == EXIT_FAILURE and "Compatibility: INCOMPATIBLE" in out and "newer PreReqAI" in out
    assert "Regeneration recommended" not in out

    # an older contract still within the compatible range: healthy, upgrade signal, untouched
    monkeypatch.setitem(metadata_module.OLDEST_COMPATIBLE, "contract_version", 0)
    _set_contract(project, 0)
    before = _tree(project)
    code, out, _ = _cli(capsys, "api-generation", "check", str(project))
    assert code == EXIT_OK and "Compatibility: UPGRADABLE" in out
    assert _tree(project) == before
    command = check_generated_project(project).compatibility["regeneration"]["command"]

    # regeneration into the same location, with the suggested command, is safe and restores the current contract
    (project / "NOTES.md").write_text("my own notes\n")  # a user file the generator does not own
    argv = shlex.split(command.replace("<validated-draft.json>", shlex.quote(str(draft_file))))
    code, _, err = _cli(capsys, *argv[3:])  # argv[:3] is "python -m backend.cli"
    assert code == EXIT_OK, err
    assert (project / "NOTES.md").read_text() == "my own notes\n"
    after = _tree(project)
    del after["NOTES.md"]
    assert after == generated_tree  # byte-identical to the first generation
    assert check_generated_project(project).compatibility["status"] == "compatible"

    # and regenerating once more (or dry-running) changes nothing
    assert _cli(capsys, *generate)[0] == EXIT_OK
    assert _cli(capsys, *generate, "--dry-run")[0] == EXIT_OK
    final = _tree(project)
    del final["NOTES.md"]
    assert final == generated_tree
