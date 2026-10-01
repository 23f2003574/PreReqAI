import subprocess
import sys

import pytest

from backend.api_generation import (
    FastAPIApplicationGenerator,
    LLMAPIGenerationResult,
    LLMAPIGenerationService,
    UnsafeGeneratedPathError,
    write_generated_application,
)
from test_api_generation_boundary import _draft, _env


def _result():
    env = _env()
    _, validated = _draft(env)
    service = LLMAPIGenerationService(env["draft"], FastAPIApplicationGenerator())
    return service.generate(validated), validated


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_text() for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def test_generated_package_imports_in_a_clean_process_and_registers_its_routes(tmp_path):
    result, _ = _result()
    written = write_generated_application(result, tmp_path)

    assert written == ["Dockerfile", "app/__init__.py", "app/main.py", "requirements.txt"]
    code = (
        "from app.main import app; "
        "print(sorted((r.path, sorted(r.methods)) for r in app.routes if r.path == '/add'))"
    )
    run = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True)

    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "[('/add', ['POST'])]"


def test_generating_twice_yields_an_identical_tree_without_junk(tmp_path):
    result, _ = _result()

    write_generated_application(result, tmp_path)
    first = _tree(tmp_path)
    write_generated_application(result, tmp_path)

    assert _tree(tmp_path) == first
    assert sorted(first) == [".prereqai-generated.json", "Dockerfile", "app/__init__.py", "app/main.py", "requirements.txt"]
    assert not list(tmp_path.rglob("*.tmp"))


@pytest.mark.parametrize("bad", ["../escape.py", "/abs.py", "app/../../escape.py"])
def test_paths_escaping_the_output_directory_are_rejected(tmp_path, bad):
    with pytest.raises(UnsafeGeneratedPathError):
        write_generated_application(LLMAPIGenerationResult("d", "POST /x", {bad: "x"}), tmp_path / "out")
    assert not (tmp_path / "escape.py").exists()
