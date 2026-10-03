"""The generation target is checked before the draft is read or anything is
generated, with the same rules for real runs and --dry-run."""
import os
import stat

import pytest

from backend.api_generation import (
    MARKER_FILENAME,
    FastAPIApplicationGenerator,
    UnsafeOutputDirectoryError,
    generate_application,
    preflight_output_dir,
)
from backend.cli import EXIT_INVALID_INPUT, EXIT_OK, main
from test_api_generation_boundary import _draft, _env
from test_api_generation_cli import drafts  # noqa: F401  (fixture)


def _setup():
    env = _env()
    return env["draft"], _draft(env)[1]


def _tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


def test_a_fresh_nested_output_directory_passes_and_nothing_is_created(tmp_path, drafts, capsys):  # noqa: F811
    target = tmp_path / "a" / "b" / "project"

    assert preflight_output_dir(target) == target.resolve() and not (tmp_path / "a").exists()
    code = main(["api-generation", "generate", "--draft", str(drafts[0]), "--output-dir", str(target), "--dry-run"])

    assert code == EXIT_OK and not (tmp_path / "a").exists()
    capsys.readouterr()


def test_an_existing_generated_project_passes_and_is_regenerated_in_place(tmp_path):
    service, draft = _setup()
    out = tmp_path / "out"
    first = generate_application(service, draft, out)

    assert preflight_output_dir(out) == out.resolve()
    assert generate_application(service, draft, out).files == first.files


def test_an_unrelated_directory_passes_preflight_and_its_files_are_preserved(tmp_path):
    service, draft = _setup()
    (tmp_path / "notes.txt").write_text("mine")

    assert preflight_output_dir(tmp_path) == tmp_path.resolve()
    generate_application(service, draft, tmp_path)

    assert (tmp_path / "notes.txt").read_text() == "mine"


def test_colliding_unrelated_files_are_refused_and_left_untouched_in_dry_run_too(tmp_path):
    service, draft = _setup()
    (tmp_path / "README.md").write_text("mine")
    before = _tree(tmp_path)

    for dry_run in (True, False):
        with pytest.raises(UnsafeOutputDirectoryError) as raised:
            generate_application(service, draft, tmp_path, dry_run=dry_run)
        assert raised.value.stage == "write"
    assert _tree(tmp_path) == before and (tmp_path / "README.md").read_text() == "mine"


def test_invalid_targets_fail_at_preflight_before_any_generation(tmp_path, monkeypatch):
    service, draft = _setup()
    calls = []
    monkeypatch.setattr(FastAPIApplicationGenerator, "generate", lambda self, d: calls.append(d))
    a_file = tmp_path / "file"
    a_file.write_text("x")
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / MARKER_FILENAME).write_text("not json")

    for target in (a_file, a_file / "sub" / "project", tmp_path / "bad"):
        for dry_run in (True, False):
            with pytest.raises(UnsafeOutputDirectoryError) as raised:
                generate_application(service, draft, target, dry_run=dry_run)
            assert raised.value.stage == "preflight"
    assert calls == []  # the generator was never asked to do any work


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write to read-only directories")
def test_an_unwritable_target_is_reported(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(UnsafeOutputDirectoryError, match="not writable"):
            preflight_output_dir(locked / "project")
    finally:
        locked.chmod(stat.S_IRWXU)


def test_cli_checks_the_output_directory_before_reading_the_draft(tmp_path, capsys):
    a_file = tmp_path / "file"
    a_file.write_text("x")

    code = main(["api-generation", "generate", "--draft", str(tmp_path / "missing.json"),
                 "--output-dir", str(a_file / "project"), "--dry-run"])

    err = capsys.readouterr().err
    assert code == EXIT_INVALID_INPUT and err.startswith("error: output conflict at stage 'preflight': UnsafeOutputDirectoryError")
    assert "is not a directory" in err and "hint: choose an output directory" in err and "cannot read a draft" not in err
