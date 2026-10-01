import subprocess
import sys

import pytest

from backend.api_generation import (
    APIGenerator,
    DraftNotValidatedError,
    GeneratedArtifactRejectedError,
    FastAPIApplicationGenerator,
    generate_application,
    require_valid,
)
from test_api_generation_boundary import _draft, _env


def test_validated_draft_flows_through_generation_validation_and_output(tmp_path):
    env = _env()  # scripted LLM -> notebook analysis -> candidate -> schemas -> recommendation -> review -> draft
    _, validated = _draft(env)

    app = generate_application(env["draft"], validated, tmp_path / "out")

    assert (app.draft_id, app.endpoint) == (validated.draft_id, "POST /add")
    assert app.files == ["Dockerfile", "app/__init__.py", "app/main.py", "openapi.json", "prereqai-manifest.json", "prereqai-project.json", "requirements.txt"]
    assert app.openapi_path == (tmp_path / "out" / "openapi.json").resolve() and app.openapi_path.is_file()
    written = {p: (app.output_dir / p).read_text() for p in app.files}
    assert require_valid(written).valid
    run = subprocess.run(
        [sys.executable, "-c", "from app.main import app; print([r.path for r in app.routes if r.path == '/add'])"],
        cwd=app.output_dir, capture_output=True, text=True,
    )
    assert run.returncode == 0 and run.stdout.strip() == "['/add']"


def test_unvalidated_draft_writes_nothing(tmp_path):
    env = _env()
    draft, _ = _draft(env)

    with pytest.raises(DraftNotValidatedError):
        generate_application(env["draft"], draft, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_generated_output_that_fails_validation_is_not_written(tmp_path):
    class BrokenGenerator(APIGenerator):
        def generate(self, draft):
            files = FastAPIApplicationGenerator().generate(draft)
            return {**files, "app/main.py": "def broken(:\n"}

    env = _env()
    _, validated = _draft(env)

    with pytest.raises(GeneratedArtifactRejectedError) as raised:
        generate_application(env["draft"], validated, tmp_path / "out", generator=BrokenGenerator())
    assert {f["category"] for f in raised.value.validation.findings} == {"SYNTAX_ERROR"}
    assert not (tmp_path / "out").exists()


def test_draft_only_callers_are_unaffected():
    env = _env()
    draft, validated = _draft(env)

    assert env["draft"].get(draft.draft_id) == validated  # generation was never required to obtain a draft


def _failing_stage(tmp_path, **kwargs):
    env = _env()
    _, validated = _draft(env)
    with pytest.raises(Exception) as raised:
        generate_application(env["draft"], validated, tmp_path / "out", **kwargs)
    return raised.value


def test_each_failure_reports_the_stage_that_failed(tmp_path, monkeypatch):
    from backend import api_generation
    from backend.api_generation import workflow

    class Bad(APIGenerator):
        def generate(self, draft):
            return {**FastAPIApplicationGenerator().generate(draft), "app/main.py": "def broken(:\n"}

    assert _failing_stage(tmp_path, generator=Bad()).stage == "validation"

    env = _env()
    draft, _ = _draft(env)
    with pytest.raises(DraftNotValidatedError) as raised:
        generate_application(env["draft"], draft, tmp_path / "out")
    assert raised.value.stage == "generation" and "stage: generation" in raised.value.__notes__[-1]

    def boom(*args):
        raise OSError("disk full")

    monkeypatch.setattr(workflow, "write_generated_application", boom)
    error = _failing_stage(tmp_path)
    assert isinstance(error, OSError) and error.stage == "write"
    assert api_generation.STAGES == ("configuration", "generation", "validation", "write")


def test_failed_run_never_returns_a_project_and_a_later_good_run_replaces_stale_files(tmp_path):
    env = _env()
    _, validated = _draft(env)
    out = tmp_path / "out"
    first = generate_application(env["draft"], validated, out)
    (out / "app" / "mine.py").write_text("user file")

    second = generate_application(env["draft"], validated, out)

    assert second.files == first.files and (out / "app" / "mine.py").read_text() == "user file"
