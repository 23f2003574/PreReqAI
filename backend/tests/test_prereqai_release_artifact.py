"""PreReqAI ships as its source tree (there is no wheel): the release artifact is
what `git archive HEAD` exports. This catches "works from source but breaks when
shipped" -- a runtime file, example or resource that exists in a working tree but
was never committed (or is git-ignored). The exported tree alone must start every
documented entry point and complete the README quickstart and the api-generation
example. The generated project itself is covered by test_generated_project_*.py."""
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("README.md", "LICENSE", "requirements.txt", "backend/cli.py", "backend/main.py", "backend/version.py",
            "examples/prerequisites/sample-paper.pdf", "examples/api-generation/draft.json")


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout: the release artifact cannot be exported")
    target = tmp_path_factory.mktemp("release")
    archive = target / "release.tar"
    subprocess.run(["git", "archive", "--format=tar", "-o", str(archive), "HEAD"], cwd=ROOT, check=True)
    with tarfile.open(archive) as bundle:
        bundle.extractall(target / "src", **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return target / "src"


def _run(release, *args):
    return subprocess.run([sys.executable, *args], cwd=release, capture_output=True, text=True, timeout=120)


def test_release_contains_the_files_the_documented_workflows_need(release):
    assert [name for name in REQUIRED if not (release / name).is_file()] == []
    assert not any(release.rglob("__pycache__")), "build caches must not ship"


def test_release_entry_points_start(release):
    cli = _run(release, "-m", "backend.cli", "--help")
    assert cli.returncode == 0 and "prerequisites" in cli.stdout, cli.stderr
    app = _run(release, "-c", "from backend.main import app; print(app.title)")
    assert app.returncode == 0 and app.stdout.strip() == "PreReqAI", app.stderr


def test_release_runs_the_quickstart_and_the_api_generation_example(release, tmp_path):
    quickstart = _run(release, "-m", "backend.cli", "prerequisites", "analyze", "examples/prerequisites/sample-paper.pdf")
    assert quickstart.returncode == 0 and quickstart.stdout.startswith("Analysed '"), quickstart.stderr

    generated = _run(release, "-m", "backend.cli", "api-generation", "generate", "--draft",
                     "examples/api-generation/draft.json", "--output-dir", str(tmp_path / "api"), "-q")
    assert generated.returncode == 0, generated.stderr
    check = _run(release, "-m", "backend.cli", "api-generation", "check", str(tmp_path / "api"))
    assert check.returncode == 0 and "HEALTHY" in check.stdout, check.stdout + check.stderr


def test_release_serves_the_http_workflow_and_reports_one_version(release):
    """The exported tree alone answers the HTTP workflow (upload -> session -> question) and the CLI and
    API report the same version."""
    probe = (
        "from fastapi.testclient import TestClient\n"
        "from backend.main import app\n"
        "c = TestClient(app)\n"
        "with open('examples/prerequisites/sample-paper.pdf', 'rb') as pdf:\n"
        "    r = c.post('/api/prerequisites/analyze', files={'paper': ('s.pdf', pdf, 'application/pdf')})\n"
        "assert r.status_code == 200 and r.json()['status'] == 'success', r.text\n"
        "q = c.post('/api/session/' + r.json()['session_id'] + '/question', json={'question': 'What is attention?'})\n"
        "assert q.status_code == 200 and q.json()['responses'], q.text\n"
        "print(app.version)\n"
    )
    served = _run(release, "-c", probe)
    assert served.returncode == 0, served.stderr
    cli = _run(release, "-m", "backend.cli", "--version")
    assert cli.returncode == 0 and cli.stdout.strip() == f"PreReqAI {served.stdout.strip()}", cli.stderr
