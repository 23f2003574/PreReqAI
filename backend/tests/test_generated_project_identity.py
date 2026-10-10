"""One resolved project identity (name -> package -> entrypoint) used by every
generated artifact: default naming, explicit naming, normalization and
validation, and cross-artifact consistency."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.api_generation import (
    APIGenerationConfig,
    FastAPIApplicationGenerator,
    InvalidProjectNameError,
    project_package,
    resolve_project_identity,
    validate_generated_artifact,
)
from backend.cli import EXIT_INVALID_INPUT, EXIT_OK, main
from backend.llm.config import InvalidConfigurationError

EXAMPLE_DRAFT = Path(__file__).resolve().parents[2] / "examples" / "api-generation" / "draft.json"


def _draft():
    from backend.cli import _load_draft
    return _load_draft(str(EXAMPLE_DRAFT))


def test_default_identity_is_the_previous_output():
    draft = _draft()
    identity = resolve_project_identity(draft)
    files = FastAPIApplicationGenerator().generate(draft)

    assert (identity.name, identity.package, identity.entrypoint) == (draft.summary, "app", "app.main:app")
    assert "app/main.py" in files and "app/__init__.py" in files
    assert json.loads(files["prereqai-manifest.json"])["application"] == {"name": draft.summary, "entrypoint": "app.main:app"}
    assert "project_name" not in json.loads(files["prereqai-project.json"])
    assert "docker build -t generated-api ." in files["README.md"]


@pytest.mark.parametrize("name, package", [
    ("loan-quote", "loan_quote"), ("Loan_Quote2", "loan_quote2"), ("LoanAPI", "loanapi"), ("q", "q"),
])
def test_explicit_names_normalize_to_importable_packages(name, package):
    assert project_package(name) == package


@pytest.mark.parametrize("name", [
    "", "2fast", "-api", "loan quote", "loan.quote", "loan/quote", "x" * 65, "class", "match",
    "json", "typing", "fastapi", "pydantic", "uvicorn", 42, None,
])
def test_names_that_cannot_be_a_safe_package_are_rejected(name):
    with pytest.raises(InvalidProjectNameError):
        project_package(name)


def test_invalid_names_are_rejected_before_generation(tmp_path, capsys):
    with pytest.raises(InvalidConfigurationError):
        APIGenerationConfig(output_dir=str(tmp_path / "x"), project_name="my api").validate()
    with pytest.raises(InvalidProjectNameError):
        FastAPIApplicationGenerator(project_name="json")

    out = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE_DRAFT), "--output-dir", str(out),
                 "--project-name", "class"]) == EXIT_INVALID_INPUT
    assert "InvalidProjectNameError" in capsys.readouterr().err and not out.exists()


def test_explicit_name_is_used_consistently_and_the_project_runs(tmp_path, capsys):
    out = tmp_path / "project"
    assert main(["api-generation", "generate", "--draft", str(EXAMPLE_DRAFT), "--output-dir", str(out),
                 "--project-name", "Loan-Quote", "--json"]) == EXIT_OK
    files = json.loads(capsys.readouterr().out)["files"]

    assert {"loan_quote/__init__.py", "loan_quote/main.py"} <= set(files) and not any(f.startswith("app/") for f in files)
    manifest = json.loads((out / "prereqai-manifest.json").read_text())
    assert manifest["application"] == {"name": "Loan-Quote", "entrypoint": "loan_quote.main:app"}
    assert json.loads((out / "prereqai-project.json").read_text())["project_name"] == "Loan-Quote"
    readme = (out / "README.md").read_text()
    assert readme.startswith("# Loan-Quote\n") and "uvicorn loan_quote.main:app" in readme
    assert "`loan_quote/main.py`" in readme and "docker build -t loan-quote ." in readme
    dockerfile = (out / "Dockerfile").read_text()
    assert "COPY loan_quote ./loan_quote" in dockerfile and "loan_quote.main:app" in dockerfile
    assert json.loads((out / "openapi.json").read_text())["info"]["title"] == "Loan-Quote"

    assert main(["api-generation", "check", str(out), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "healthy"
    probe = subprocess.run(
        [sys.executable, "-c", "from fastapi.testclient import TestClient; from loan_quote.main import app; "
                               "print(TestClient(app).get('/openapi.json').json()['info']['title'])"],
        cwd=out, capture_output=True, text=True,
    )
    assert probe.returncode == 0 and probe.stdout.strip() == "Loan-Quote", probe.stderr


def test_disagreeing_identity_across_artifacts_is_rejected():
    files = FastAPIApplicationGenerator(project_name="loan-quote").generate(_draft())
    assert validate_generated_artifact(files).valid

    renamed = json.loads(files["prereqai-manifest.json"])
    renamed["application"]["name"] = "other-name"
    tampered = {**files, "prereqai-manifest.json": json.dumps(renamed, indent=2, sort_keys=True) + "\n"}
    assert "IDENTITY_MISMATCH" in {f["category"] for f in validate_generated_artifact(tampered).findings}

    metadata = json.loads(files["prereqai-project.json"])
    del metadata["project_name"]  # metadata now claims the default `app` package
    tampered = {**files, "prereqai-project.json": json.dumps(metadata, indent=2, sort_keys=True) + "\n"}
    assert "IDENTITY_MISMATCH" in {f["category"] for f in validate_generated_artifact(tampered).findings}
