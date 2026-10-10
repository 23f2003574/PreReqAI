"""A generated project validates and imports from a clean copy of itself: only
the artifacts its manifest declares (plus the manifest), with no generation
marker, no bytecode caches, no temporary files and no earlier generation's
leftovers -- and outside the PreReqAI source tree."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend.api_generation import PROJECT_MANIFEST_FILENAME, check_generated_project
from backend.api_generation.writer import MARKER_FILENAME
from backend.cli import EXIT_OK, main
from test_generated_project_importability import EXAMPLE, REPO_ROOT, _probe


def _generate(out, capsys, *extra):
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"),
                 "--output-dir", str(out), *extra]) == EXIT_OK
    capsys.readouterr()


def _all_files(root: Path) -> set:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def _clean_copy(project: Path, destination: Path) -> Path:
    """Exactly the declared project: manifest artifacts + the manifest itself."""
    manifest = json.loads((project / PROJECT_MANIFEST_FILENAME).read_text())
    for relative in [a["path"] for a in manifest["artifacts"]] + [PROJECT_MANIFEST_FILENAME]:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project / relative, target)
    return destination


def _transient(root: Path) -> set:
    return {
        p for p in _all_files(root)
        if "__pycache__" in p.split("/") or p.endswith((".tmp", ".pyc")) or p == MARKER_FILENAME
    }


@pytest.mark.parametrize("extra, package", [((), "app"), (("--project-name", "loan-quote"), "loan_quote")])
def test_declared_artifacts_alone_are_a_valid_importable_project(tmp_path, capsys, extra, package):
    project = tmp_path / "generated"
    _generate(project, capsys, *extra)

    # the only file generation adds beyond the declared project is its ownership marker
    assert _transient(project) == {MARKER_FILENAME}
    _probe(project, package)  # importing creates bytecode caches in the output...
    assert any("__pycache__" in p for p in _transient(project))

    clean = _clean_copy(project, tmp_path / "clean")  # ...which a clean copy does not carry
    assert _transient(clean) == set() and not clean.resolve().is_relative_to(REPO_ROOT)
    assert _all_files(clean) == _all_files(project) - _transient(project)

    health = check_generated_project(clean)
    assert health.healthy, health.findings
    seen = _probe(clean, package)
    assert seen["blocked"] == [] and seen["host_modules"] == []


def test_cleaning_caches_and_marker_in_place_keeps_the_project_valid(tmp_path, capsys):
    project = tmp_path / "generated"
    _generate(project, capsys)
    _probe(project, "app")

    for relative in sorted(_transient(project), reverse=True):
        (project / relative).unlink()
    for cache in project.rglob("__pycache__"):
        shutil.rmtree(cache)

    assert check_generated_project(project).healthy
    _probe(project, "app")


def test_regeneration_leaves_no_stale_artifacts_from_the_previous_project(tmp_path, capsys):
    """Regenerating under a new project name moves the app to a new package;
    the old package (even with bytecode caches beside it) must not survive as
    a second application or make the project invalid."""
    project = tmp_path / "generated"
    _generate(project, capsys)
    _probe(project, "app")  # leaves app/__pycache__ behind

    _generate(project, capsys, "--project-name", "loan-quote")

    assert not (project / "app").exists()
    assert {p for p in _all_files(project) if p.endswith(".py")} == {"loan_quote/__init__.py", "loan_quote/main.py"}
    assert check_generated_project(project).healthy
    clean = _clean_copy(project, tmp_path / "clean")
    assert check_generated_project(clean).healthy
    _probe(clean, "loan_quote")


def test_a_fresh_interpreter_needs_no_state_from_the_generating_process(tmp_path, capsys):
    """Generation and checking run in separate processes, from a directory
    outside the repository, so no in-process cache or module state is reused."""
    project = tmp_path / "generated"
    _generate(project, capsys)
    clean = _clean_copy(project, tmp_path / "clean")
    run = subprocess.run(
        [sys.executable, "-m", "backend.cli", "api-generation", "check", str(clean), "--json"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == 0 and json.loads(run.stdout)["status"] == "healthy", run.stdout + run.stderr
