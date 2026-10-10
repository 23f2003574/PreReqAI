"""Generated projects are separate from PreReqAI's own development
environment: generating needs nothing from the repository beyond the
generator code itself (in particular not its development requirements.txt),
no development or test setting leaks into the output, and the generated
configuration loads on its own from an isolated output directory."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from backend.api_generation import CONFIG_FILENAME
from backend.cli import EXIT_OK, main
from test_generated_project_clean_build import _clean_copy
from test_generated_project_importability import EXAMPLE, REPO_ROOT

DEV_ONLY = ("pytest", "pymupdf", "pdfplumber", "requests", "httpx", "python-multipart")


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def test_generation_does_not_read_the_host_repository_environment(tmp_path):
    """The generator, copied away from the repository (no requirements.txt,
    README, docs or examples beside it) and run in an isolated interpreter,
    produces exactly the committed example project. (-E, not -I: the
    generator's own dependencies may live in the user site-packages; PYTHONPATH
    is still ignored and the working directory is outside the repository.)"""
    host = tmp_path / "host"
    shutil.copytree(REPO_ROOT / "backend", host / "backend",
                    ignore=shutil.ignore_patterns("__pycache__", "tests", "*.pyc"))
    shutil.copyfile(EXAMPLE / "draft.json", tmp_path / "draft.json")
    assert not (host / "requirements.txt").exists()

    run = subprocess.run(
        [sys.executable, "-E", "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); from backend.cli import main; "
         "assert all(not p.startswith(sys.argv[4]) for p in sys.path), sys.path; "
         "sys.exit(main(['api-generation', 'generate', '--draft', sys.argv[2], '--output-dir', sys.argv[3]]))",
         str(host), str(tmp_path / "draft.json"), str(tmp_path / "out"), str(REPO_ROOT)],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )
    assert run.returncode == 0, run.stderr
    assert _tree(tmp_path / "out") == _tree(EXAMPLE / "generated")


def test_no_development_or_machine_setting_leaks_into_the_project(tmp_path, capsys):
    out = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"),
                 "--output-dir", str(out), "--project-name", "loan-quote"]) == EXIT_OK
    capsys.readouterr()

    requirements = (out / "requirements.txt").read_text().lower()
    assert requirements.splitlines() == ["fastapi>=0.115.0", "pydantic>=2.0", "uvicorn>=0.32.0"]
    assert not any(dev in requirements for dev in DEV_ONLY)

    for relative, content in _tree(out).items():
        text = content.decode("utf-8")
        for machine_specific in (str(REPO_ROOT), str(tmp_path), str(Path.home()), "output_dir", "PYTEST", "pytest"):
            assert machine_specific not in text, (relative, machine_specific)


def test_generated_configuration_loads_alone_from_an_isolated_directory(tmp_path, capsys):
    out = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"), "--output-dir", str(out)]) == EXIT_OK
    capsys.readouterr()
    clean = _clean_copy(out, tmp_path / "clean")

    # the standard library alone, no PreReqAI import path, cwd = the project
    run = subprocess.run(
        [sys.executable, "-I", "-c",
         "import json, sys; print(json.dumps([json.load(open(sys.argv[1])), "
         "sorted(m for m in sys.modules if m.split('.')[0] in ('backend', 'frontend'))]))",
         CONFIG_FILENAME],
        cwd=clean, capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == 0, run.stderr
    config, host_modules = json.loads(run.stdout)

    assert host_modules == []
    assert config == {"config_version": 1, "generation": {"project_name": None},
                      "runtime": {"base_image": "python:3.11-slim", "port": 8000}}
    # runtime defaults the project itself uses agree with the file
    dockerfile = (clean / "Dockerfile").read_text()
    assert dockerfile.startswith("FROM python:3.11-slim\n") and "ENV HOST=0.0.0.0 PORT=8000" in dockerfile
    assert "--port 8000" in (clean / "README.md").read_text()


def test_generator_only_settings_stay_out_of_the_runtime_section(tmp_path, capsys):
    out = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"), "--output-dir", str(out),
                 "--project-name", "loan-quote", "--port", "9100"]) == EXIT_OK
    capsys.readouterr()
    config = json.loads((out / CONFIG_FILENAME).read_text())

    assert set(config) == {"config_version", "generation", "runtime"}
    assert config["generation"] == {"project_name": "loan-quote"}
    assert config["runtime"] == {"base_image": "python:3.11-slim", "port": 9100}
