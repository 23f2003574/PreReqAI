import json
import pytest

from backend.api_generation import (
    COMPLETE,
    INCOMPLETE,
    MARKER_FILENAME,
    LLMAPIGenerationResult,
    UnsafeOutputDirectoryError,
    generate_application,
    generation_status,
    write_generated_application,
)
from backend.cli import EXIT_INVALID_INPUT, main
from test_api_generation_boundary import _draft, _env
from test_api_generation_cli import drafts  # noqa: F401  (fixture)


def _files(**extra):
    return LLMAPIGenerationResult("d", "POST /x", {"app/main.py": "a", "app/__init__.py": "", "Dockerfile": "d", **extra})


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_text() for p in sorted(root.rglob("*")) if p.is_file()}


def test_clean_generation_into_a_new_or_empty_directory(tmp_path):
    write_generated_application(_files(), tmp_path / "new")
    (tmp_path / "empty").mkdir()
    write_generated_application(_files(), tmp_path / "empty")

    for name in ("new", "empty"):
        assert generation_status(tmp_path / name) == COMPLETE
        assert (tmp_path / name / "app" / "main.py").read_text() == "a"


def test_repeat_generation_is_deterministic(tmp_path):
    write_generated_application(_files(), tmp_path)
    first = _tree(tmp_path)

    write_generated_application(_files(), tmp_path)

    assert _tree(tmp_path) == first


def test_stale_generated_files_are_removed_and_unrelated_files_survive(tmp_path):
    write_generated_application(_files(**{"app/old_route.py": "old", "extra/x.txt": "x"}), tmp_path)
    (tmp_path / "notes.txt").write_text("mine")
    (tmp_path / "app" / "mine.py").write_text("also mine")

    write_generated_application(_files(), tmp_path)

    assert not (tmp_path / "app" / "old_route.py").exists() and not (tmp_path / "extra").exists()
    assert (tmp_path / "notes.txt").read_text() == "mine" and (tmp_path / "app" / "mine.py").read_text() == "also mine"
    assert json.loads((tmp_path / MARKER_FILENAME).read_text())["files"] == ["Dockerfile", "app/__init__.py", "app/main.py"]


def test_unrelated_files_alone_do_not_block_generation(tmp_path):
    (tmp_path / "README.md").write_text("mine")

    write_generated_application(_files(), tmp_path)

    assert (tmp_path / "README.md").read_text() == "mine" and (tmp_path / "app" / "main.py").exists()


def test_unmarked_directory_with_colliding_files_is_refused_and_untouched(tmp_path):
    (tmp_path / "Dockerfile").write_text("the user's own Dockerfile")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("the user's own app")

    with pytest.raises(UnsafeOutputDirectoryError):
        write_generated_application(_files(), tmp_path)

    assert _tree(tmp_path) == {"Dockerfile": "the user's own Dockerfile", "app/main.py": "the user's own app"}


def test_unreadable_marker_is_refused(tmp_path):
    (tmp_path / MARKER_FILENAME).write_text("not json")

    with pytest.raises(UnsafeOutputDirectoryError):
        write_generated_application(_files(), tmp_path)


def test_interrupted_regeneration_is_marked_incomplete_never_complete(tmp_path, monkeypatch):
    import backend.api_generation.writer as writer

    write_generated_application(_files(), tmp_path)
    real = writer._atomic_write
    calls = {"n": 0}

    def flaky(target, text):
        calls["n"] += 1
        if calls["n"] == 3:  # marker, first file, then fail on the second
            raise OSError("disk full")
        real(target, text)

    monkeypatch.setattr(writer, "_atomic_write", flaky)
    with pytest.raises(OSError):
        write_generated_application(_files(), tmp_path)
    monkeypatch.undo()

    assert generation_status(tmp_path) == INCOMPLETE
    write_generated_application(_files(), tmp_path)  # an incomplete run can be redone over itself
    assert generation_status(tmp_path) == COMPLETE


def test_workflow_refuses_unsafe_output_directory_at_the_write_stage(tmp_path):
    env = _env()
    _, validated = _draft(env)
    (tmp_path / "Dockerfile").write_text("mine")

    with pytest.raises(UnsafeOutputDirectoryError) as raised:
        generate_application(env["draft"], validated, tmp_path)

    assert raised.value.stage == "write" and (tmp_path / "Dockerfile").read_text() == "mine"
    assert not (tmp_path / "app").exists()


def test_cli_reports_the_refusal_and_leaves_the_directory_alone(tmp_path, drafts, capsys):  # noqa: F811
    (tmp_path / "requirements.txt").write_text("mine")

    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(tmp_path)])

    err = capsys.readouterr().err
    assert code == EXIT_INVALID_INPUT and "stage 'write'" in err and "UnsafeOutputDirectoryError" in err
    assert (tmp_path / "requirements.txt").read_text() == "mine"
