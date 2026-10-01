"""Final integration smoke: the supported product path, end to end, through the
real CLI and orchestration -- scripted notebook workflow -> validated draft ->
`api-generation` CLI (dry run, generate, check) -> generated project -> release
checklist -- plus a second generation and a representative failure."""
import json
import subprocess
import sys
from dataclasses import asdict

from backend.api_generation import APIGenerator, FastAPIApplicationGenerator, run_release_checklist
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from test_api_generation_boundary import _draft, _env


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def test_supported_generation_path_end_to_end(tmp_path, capsys):
    env = _env()
    draft_obj, validated = _draft(env)
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps(asdict(validated)))
    out = tmp_path / "project"

    # dry run: reports the plan, filesystem unchanged
    assert main(["api-generation", "generate", "--draft", str(draft_file), "--output-dir", str(out), "--dry-run", "--json"]) == EXIT_OK
    planned = json.loads(capsys.readouterr().out)
    assert planned["dry_run"] is True and not out.exists()

    # real generation through the CLI
    assert main(["api-generation", "generate", "--draft", str(draft_file), "--output-dir", str(out), "--json"]) == EXIT_OK
    generated = json.loads(capsys.readouterr().out)
    assert generated["files"] == planned["files"] and generated["endpoint"] == "POST /add"
    first = _tree(out)

    # the project is healthy on disk and its generated app, OpenAPI and README agree
    assert main(["api-generation", "check", str(out), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "healthy"
    probe = subprocess.run(
        [sys.executable, "-c",
         "import json; from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); "
         "print(json.dumps([c.get('/openapi.json').json()['paths'], c.post('/add', json={'a': 1, 'b': 2}).json()], sort_keys=True))"],
        cwd=out, capture_output=True, text=True,
    )
    paths, answer = json.loads(probe.stdout)
    assert probe.returncode == 0 and list(paths) == ["/add"] and answer == {"sum": 3}
    assert paths == json.loads((out / "openapi.json").read_text())["paths"]
    manifest = json.loads((out / "prereqai-manifest.json").read_text())
    readme = (out / "README.md").read_text()
    assert all(f"`{a['path']}`" in readme for a in manifest["artifacts"]) and "app.main:app" in readme

    # release checklist: ready, and it wrote nothing into the working directory
    checklist = run_release_checklist(env["draft"], validated)
    assert checklist.ready and checklist.failures == [] and len(checklist.checks) == 9

    # a second generation is safe and deterministic; a dry run afterwards changes nothing
    assert main(["api-generation", "generate", "--draft", str(draft_file), "--output-dir", str(out)]) == EXIT_OK
    assert _tree(out) == first
    assert main(["api-generation", "generate", "--draft", str(draft_file), "--output-dir", str(out), "--dry-run"]) == EXIT_OK
    assert _tree(out) == first
    capsys.readouterr()


def test_representative_failures_are_not_ready_and_leave_no_misleading_output(tmp_path, capsys):
    env = _env()
    _, validated = _draft(env)
    bad_endpoint = tmp_path / "bad.json"
    bad_endpoint.write_text(json.dumps({**asdict(validated), "endpoint": "FETCH /add"}))
    out = tmp_path / "project"

    assert main(["api-generation", "generate", "--draft", str(bad_endpoint), "--output-dir", str(out)]) == EXIT_FAILURE
    assert "InvalidDraftEndpointError" in capsys.readouterr().err and not out.exists()

    class Corrupt(APIGenerator):
        def generate(self, draft):
            return {**FastAPIApplicationGenerator().generate(draft), "app/main.py": "def broken(:\n"}

    checklist = run_release_checklist(env["draft"], validated, Corrupt())
    assert not checklist.ready and any("SYNTAX_ERROR" in f for f in checklist.failures)
    assert not out.exists()
