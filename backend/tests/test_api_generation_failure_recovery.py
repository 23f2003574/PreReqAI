import pytest

import backend.api_generation.writer as writer
from backend.api_generation import (
    COMPLETE,
    INCOMPLETE,
    MARKER_FILENAME,
    APIGenerationConfig,
    APIGenerator,
    FastAPIApplicationGenerator,
    GeneratedArtifactRejectedError,
    check_generated_project,
    generate_application,
    generation_status,
)
from backend.llm.config import InvalidConfigurationError
from test_api_generation_boundary import _draft, _env


def _setup():
    env = _env()
    _, validated = _draft(env)
    return env["draft"], validated


def _tree(root):
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def _fail_on_write(monkeypatch, number):
    real, calls = writer._atomic_write, {"n": 0}

    def flaky(target, text):
        calls["n"] += 1
        if calls["n"] == number:
            raise OSError("disk full")
        real(target, text)

    monkeypatch.setattr(writer, "_atomic_write", flaky)


def test_early_stage_failures_touch_nothing_and_name_their_stage(tmp_path):
    service, draft = _setup()
    out = tmp_path / "out"
    out.mkdir()
    (out / "notes.txt").write_text("mine")

    class Broken(APIGenerator):
        def generate(self, draft):
            return {**FastAPIApplicationGenerator().generate(draft), "app/main.py": "def broken(:\n"}

    with pytest.raises(InvalidConfigurationError) as config_error:
        generate_application(service, draft, config=APIGenerationConfig(str(out), port=0))
    with pytest.raises(GeneratedArtifactRejectedError) as validation_error:
        generate_application(service, draft, out, generator=Broken())

    assert (config_error.value.stage, validation_error.value.stage) == ("configuration", "validation")
    assert _tree(out) == {"notes.txt"}


def test_failure_after_some_artifacts_were_written_removes_only_what_the_attempt_created(tmp_path, monkeypatch):
    service, draft = _setup()
    out = tmp_path / "out"
    out.mkdir()
    (out / "notes.txt").write_text("mine")
    _fail_on_write(monkeypatch, 4)  # marker + two files written, the third fails

    with pytest.raises(OSError) as raised:
        generate_application(service, draft, out)

    assert raised.value.stage == "write" and any("cleaned up" in n for n in raised.value.__notes__)
    assert _tree(out) == {"notes.txt"} and (out / "notes.txt").read_text() == "mine"
    assert not any(out.rglob("*.tmp")) and not (out / "app").exists()


def test_failed_first_generation_into_a_new_directory_leaves_nothing_behind(tmp_path, monkeypatch):
    service, draft = _setup()
    out = tmp_path / "new" / "project"
    _fail_on_write(monkeypatch, 5)

    with pytest.raises(OSError):
        generate_application(service, draft, out)

    assert not out.exists()  # the directory it created is gone too; the pre-existing parent stays
    assert (tmp_path / "new").is_dir()


def test_failed_regeneration_is_marked_incomplete_then_a_later_run_succeeds(tmp_path, monkeypatch):
    service, draft = _setup()
    out = tmp_path / "out"
    first = generate_application(service, draft, out)
    (out / "notes.txt").write_text("mine")
    _fail_on_write(monkeypatch, 4)

    with pytest.raises(OSError):
        generate_application(service, draft, out)
    monkeypatch.undo()

    assert generation_status(out) == INCOMPLETE
    assert not check_generated_project(out).healthy
    assert "INCOMPLETE_GENERATION" in {f["category"] for f in check_generated_project(out).findings}
    assert (out / "notes.txt").read_text() == "mine" and {p for p in first.files} <= _tree(out)  # nothing pre-existing lost

    again = generate_application(service, draft, out)
    assert again.files == first.files and generation_status(out) == COMPLETE
    assert check_generated_project(out).healthy and (out / "notes.txt").read_text() == "mine"


def test_cleanup_is_idempotent(tmp_path):
    root = tmp_path / "out"
    created = root / "app" / "main.py"
    created.parent.mkdir(parents=True)
    created.write_text("x")
    (root / MARKER_FILENAME).write_text("{}")

    for _ in range(2):
        writer._clean_up_failed_attempt(root, False, False, [created], [created.parent], set())

    assert not root.exists()
