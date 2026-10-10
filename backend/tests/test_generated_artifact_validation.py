import pytest

from backend.api_generation import (
    GeneratedArtifactRejectedError,
    require_valid,
    validate_generated_artifact,
)
from backend.api_schema_review import APPROVED, REJECTED
from test_generated_application_entrypoint import _result


def _files():
    result, _ = _result()
    return dict(result.files)


def _categories(files):
    return {f["category"] for f in validate_generated_artifact(files).findings}


def test_untouched_generator_output_is_approved_with_no_findings():
    validation = validate_generated_artifact(_files())

    assert validation.status == APPROVED and validation.valid and validation.findings == []
    assert require_valid(_files()).valid


@pytest.mark.parametrize("missing", ["app/main.py", "requirements.txt", "Dockerfile", "app/__init__.py"])
def test_missing_required_file_is_reported(missing):
    files = _files()
    del files[missing]

    assert "MISSING_FILE" in _categories(files)


@pytest.mark.parametrize("empty", ["app/main.py", "requirements.txt", "Dockerfile"])
def test_empty_generated_file_is_reported(empty):
    assert "EMPTY_FILE" in _categories({**_files(), empty: "  \n"})


def test_syntax_error_is_reported_and_dependent_checks_are_skipped():
    files = {**_files(), "app/main.py": "def broken(:\n"}

    validation = validate_generated_artifact(files)

    assert {f["category"] for f in validation.findings} == {"SYNTAX_ERROR"}
    assert validation.status == REJECTED


def test_module_that_fails_to_import_is_reported():
    assert "IMPORT_ERROR" in _categories({**_files(), "app/main.py": "import definitely_not_installed_pkg\n"})


def test_module_without_an_app_or_routes_is_reported():
    assert "NO_ENTRYPOINT" in _categories({**_files(), "app/main.py": "x = 1\n"})
    bare = "from fastapi import FastAPI\napp = FastAPI()\n"
    assert "NO_ROUTES" in _categories({**_files(), "app/main.py": bare})


def test_manifest_out_of_step_with_imports_is_reported():
    assert "MANIFEST_MISMATCH" in _categories({**_files(), "requirements.txt": "fastapi>=0.115.0\n"})


def test_dockerfile_not_matching_the_generated_files_is_reported():
    files = _files()
    broken = files["Dockerfile"].replace("COPY app ./app", "COPY src ./src").replace("app.main:app", "service.main:app")

    cats = _categories({**files, "Dockerfile": broken})

    assert {"DOCKER_COPY_SOURCE", "DOCKER_ENTRYPOINT"} <= cats


def test_several_independent_problems_are_all_reported_and_require_valid_raises():
    files = {**_files(), "requirements.txt": "", "Dockerfile": "FROM scratch\n"}

    validation = validate_generated_artifact(files)

    assert {"EMPTY_FILE", "MANIFEST_MISMATCH", "DOCKER_ENTRYPOINT", "DOCKER_INSTALL"} <= {
        f["category"] for f in validation.findings
    }
    with pytest.raises(GeneratedArtifactRejectedError) as raised:
        require_valid(files)
    assert raised.value.validation.findings == validation.findings and all(f["blocking"] for f in validation.findings)
