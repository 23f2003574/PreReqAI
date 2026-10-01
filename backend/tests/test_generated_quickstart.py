"""Structural check that the generated README's instructions match the files
the real workflow actually wrote: every referenced file exists, every command
points at generated artifacts, and the claimed manifest/metadata/OpenAPI
references are real. Nothing is installed or launched."""
import json
import re
import subprocess
import sys

from backend.api_generation import generate_application
from test_api_generation_boundary import _draft, _env


def _project(tmp_path):
    env = _env()
    _, validated = _draft(env)
    app = generate_application(env["draft"], validated, tmp_path / "project")
    return app.output_dir, (app.output_dir / "README.md").read_text()


def _commands(readme):
    blocks = re.findall(r"```\n(.*?)```", readme, flags=re.DOTALL)
    return [line.strip() for block in blocks for line in block.splitlines() if line.strip()]


def test_every_file_the_readme_references_exists(tmp_path):
    root, readme = _project(tmp_path)

    referenced = {m for m in re.findall(r"`([^`\s]+)`", readme) if re.search(r"\.(py|json|txt|md)$|^Dockerfile$", m)}

    assert {"requirements.txt", "openapi.json", "prereqai-project.json", "prereqai-manifest.json", "app/main.py",
            "Dockerfile", "README.md"} <= referenced
    assert [p for p in referenced if not (root / p).is_file()] == []


def test_install_command_uses_the_generated_requirements_file(tmp_path):
    root, readme = _project(tmp_path)
    [install] = [c for c in _commands(readme) if c.startswith("pip install")]

    requirements = (root / install.split("-r ")[1]).read_text().splitlines()

    assert install == "pip install -r requirements.txt"
    imports = set(re.findall(r"^(?:from|import) (\w+)", (root / "app" / "main.py").read_text(), flags=re.MULTILINE))
    assert {"fastapi", "pydantic"} <= imports and all(any(r.startswith(d) for r in requirements) for d in ("fastapi", "pydantic"))
    assert any(r.startswith("uvicorn") for r in requirements)  # the server the run command invokes


def test_run_command_targets_an_importable_generated_app_on_the_generated_port(tmp_path):
    root, readme = _project(tmp_path)
    [run] = [c for c in _commands(readme) if c.startswith("uvicorn")]
    target, port = re.match(r"uvicorn (\S+) --host 0\.0\.0\.0 --port (\d+)$", run).groups()
    module, attribute = target.split(":")
    dockerfile = (root / "Dockerfile").read_text()

    assert (root / (module.replace(".", "/") + ".py")).is_file()
    probe = subprocess.run(
        [sys.executable, "-c", f"import {module} as m; assert hasattr(m, '{attribute}')"], cwd=root, capture_output=True, text=True
    )
    assert probe.returncode == 0, probe.stderr
    assert f"PORT={port}" in dockerfile and f"EXPOSE {port}" in dockerfile and f"{target} " in dockerfile


def test_docker_commands_match_the_generated_dockerfile(tmp_path):
    root, readme = _project(tmp_path)
    build = next(c for c in _commands(readme) if c.startswith("docker build"))
    run = next(c for c in _commands(readme) if c.startswith("docker run"))
    dockerfile = (root / "Dockerfile").read_text()
    base_image = re.search(r"^FROM (\S+)$", dockerfile, flags=re.MULTILINE).group(1)
    port = re.search(r"^EXPOSE (\d+)$", dockerfile, flags=re.MULTILINE).group(1)

    assert build.endswith(" .") and (root / "Dockerfile").is_file()  # build context is the project root
    assert re.search(rf"-p {port}:{port} ", run) and run.split()[-1] == build.split("-t ")[1].split()[0]
    assert f"`{base_image}`" in readme


def test_claimed_openapi_docs_manifest_and_metadata_references_are_real(tmp_path):
    root, readme = _project(tmp_path)
    manifest = json.loads((root / "prereqai-manifest.json").read_text())
    metadata = json.loads((root / manifest["metadata_file"]).read_text())
    openapi = json.loads((root / "openapi.json").read_text())
    probe = subprocess.run(
        [sys.executable, "-c", "from app.main import app; print(sorted(r.path for r in app.routes))"],
        cwd=root, capture_output=True, text=True,
    )

    assert f"`{manifest['metadata_file']}`" in readme and metadata["endpoint"] in readme
    assert "/docs" in probe.stdout  # the interactive docs the README mentions are registered
    method, path = metadata["endpoint"].split(" ")
    assert method.lower() in openapi["paths"][path]  # the documented endpoint is in the OpenAPI file
    listed = set(re.findall(r"^\| `([^`]+)` \|", readme, flags=re.MULTILINE))
    assert listed == {a["path"] for a in manifest["artifacts"]}  # the README's file table equals the manifest inventory
