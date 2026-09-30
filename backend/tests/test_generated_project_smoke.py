"""Whole-path smoke: the scripted notebook workflow -> validated documentation
draft -> generate_application() (generation, manifest, Dockerfile, artifact
validation, OpenAPI contract) -> the written project imported and exercised in
a clean Python process. No network, Docker daemon or deployment involved."""
import json
import subprocess
import sys

from backend.api_generation import generate_application, require_valid
from test_api_generation_boundary import _draft, _env

PROBE = """
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
print(json.dumps({
    "openapi": client.get("/openapi.json").json(),
    "add": [client.post("/add", json={"a": 1, "b": 2}).json(), client.post("/add", json={"a": 1}).status_code],
}, sort_keys=True))
"""


def test_notebook_workflow_produces_a_coherent_importable_api_project(tmp_path):
    env = _env()
    _, validated = _draft(env)

    project = generate_application(env["draft"], validated, tmp_path / "project")

    on_disk = {p: (project.output_dir / p).read_text() for p in project.files}
    assert require_valid(on_disk).valid
    assert sorted(on_disk) == ["Dockerfile", "app/__init__.py", "app/main.py", "requirements.txt"]
    assert on_disk["requirements.txt"].splitlines() == ["fastapi>=0.115.0", "pydantic>=2.0", "uvicorn>=0.32.0"]
    assert "COPY app ./app" in on_disk["Dockerfile"] and "app.main:app" in on_disk["Dockerfile"]

    run = subprocess.run([sys.executable, "-c", PROBE], cwd=project.output_dir, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    observed = json.loads(run.stdout)

    assert list(observed["openapi"]["paths"]) == ["/add"] and list(observed["openapi"]["paths"]["/add"]) == ["post"]
    assert observed["openapi"]["paths"]["/add"]["post"]["summary"] == validated.summary
    assert observed["openapi"] == json.loads(project.openapi_path.read_text())  # written contract == served contract
    assert observed["add"] == [{"sum": 3}, 422]  # documented example output; invalid request rejected
