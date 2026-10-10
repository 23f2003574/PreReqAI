import shutil
import subprocess

import pytest

from backend.api_generation import InvalidDockerInputError, generate_dockerfile, write_generated_application
from test_generated_application_entrypoint import _result


def test_dockerfile_installs_the_generated_manifest_and_serves_the_generated_entrypoint():
    result, _ = _result()
    lines = result.files["Dockerfile"].splitlines()

    assert lines[0] == "FROM python:3.11-slim"
    assert lines.index("COPY requirements.txt ./") < lines.index("RUN pip install --no-cache-dir -r requirements.txt")
    assert lines.index("RUN pip install --no-cache-dir -r requirements.txt") < lines.index("COPY app ./app")
    assert "uvicorn app.main:app" in lines[-1] and "$HOST" in lines[-1] and "$PORT" in lines[-1]
    assert "ENV HOST=0.0.0.0 PORT=8000" in lines and "EXPOSE 8000" in lines


def test_dockerfile_is_deterministic_and_has_no_machine_specific_paths():
    result, _ = _result()
    text = result.files["Dockerfile"]

    assert generate_dockerfile(result.files) == text
    assert "/home/" not in text and "/tmp" not in text and "/user" not in text


def test_every_copied_source_is_a_generated_file():
    result, _ = _result()
    copied = [line.split()[1] for line in result.files["Dockerfile"].splitlines() if line.startswith("COPY ")]

    assert copied == ["requirements.txt", "app"]
    assert "requirements.txt" in result.files and any(p.startswith("app/") for p in result.files)


@pytest.mark.parametrize("drop", ["requirements.txt", "app/main.py"])
def test_missing_generated_files_are_rejected(drop):
    result, _ = _result()
    files = {k: v for k, v in result.files.items() if k != drop}

    with pytest.raises(InvalidDockerInputError):
        generate_dockerfile(files)


def test_manifest_without_the_asgi_server_is_rejected():
    result, _ = _result()

    with pytest.raises(InvalidDockerInputError):
        generate_dockerfile({**result.files, "requirements.txt": "fastapi\n"})


@pytest.mark.skipif(
    shutil.which("docker") is None or subprocess.run(["docker", "info"], capture_output=True).returncode != 0,
    reason="no reachable Docker daemon",
)
def test_dockerfile_builds_when_docker_is_available(tmp_path):
    result, _ = _result()
    write_generated_application(result, tmp_path)

    build = subprocess.run(["docker", "build", "--quiet", str(tmp_path)], capture_output=True, text=True, timeout=600)

    assert build.returncode == 0, build.stderr
