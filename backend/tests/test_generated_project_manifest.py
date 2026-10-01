import json
import re

import pytest

from backend.api_generation import (
    CONTRACT_VERSION,
    ENTRYPOINT,
    METADATA_FILENAME,
    PROJECT_MANIFEST_FILENAME,
    FastAPIApplicationGenerator,
    GeneratedProjectManifest,
    InvalidProjectManifestError,
    validate_generated_artifact,
)
from test_generated_application_entrypoint import _result


def _files(**generator):
    result, draft = _result()
    if generator:
        return FastAPIApplicationGenerator(**generator).generate(draft), draft
    return dict(result.files), draft


def _categories(files):
    return {f["category"] for f in validate_generated_artifact(files).findings}


def test_manifest_inventories_exactly_the_generated_artifacts_without_duplicating_identity():
    files, draft = _files()

    data = json.loads(files[PROJECT_MANIFEST_FILENAME])

    assert data["application"] == {"name": draft.summary, "entrypoint": ENTRYPOINT}
    assert data["metadata_file"] == METADATA_FILENAME and data["contract_version"] == CONTRACT_VERSION
    assert data["configuration"] == {"base_image": "python:3.11-slim", "port": 8000}
    assert [(a["path"], a["type"]) for a in data["artifacts"]] == [
        ("Dockerfile", "container-image"), ("app/__init__.py", "application-source"),
        ("app/main.py", "application-source"), ("openapi.json", "openapi-contract"),
        ("prereqai-project.json", "project-metadata"), ("requirements.txt", "dependency-manifest"),
    ]
    assert "draft_id" not in data and "endpoint" not in data  # identity stays in the metadata file


def test_manifest_is_deterministic_and_reflects_the_configuration():
    first, _ = _files()
    second, _ = _files()
    other, _ = _files(base_image="python:3.12-slim", port=9000)

    assert first[PROJECT_MANIFEST_FILENAME] == second[PROJECT_MANIFEST_FILENAME]
    assert json.loads(other[PROJECT_MANIFEST_FILENAME])["configuration"] == {"base_image": "python:3.12-slim", "port": 9000}
    assert validate_generated_artifact(other).valid


def test_manifest_holds_no_absolute_paths_timestamps_or_environment():
    text = _files()[0][PROJECT_MANIFEST_FILENAME]

    assert not re.search(r'"/|/home|/tmp|\d{4}-\d{2}-\d{2}T|environ|secret|token', text)


def test_manifest_parses_and_round_trips():
    text = _files()[0][PROJECT_MANIFEST_FILENAME]

    assert GeneratedProjectManifest.parse(text).to_json() == text


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: {**d, "manifest_version": 2},
        lambda d: {**d, "contract_version": 99},
        lambda d: {**d, "extra": 1},
        lambda d: {**d, "metadata_file": "other.json"},
        lambda d: {**d, "application": {"name": "", "entrypoint": "app.main:app"}},
        lambda d: {**d, "application": {"name": "x", "entrypoint": "other:app"}},
        lambda d: {**d, "artifacts": [{"path": "/etc/passwd", "type": "container-image"}]},
        lambda d: {**d, "artifacts": [{"path": "../x.py", "type": "application-source"}]},
        lambda d: {**d, "artifacts": [{"path": "Dockerfile", "type": "wrong-type"}]},
        lambda d: {**d, "artifacts": list(reversed(d["artifacts"]))},
    ],
)
def test_invalid_manifests_are_rejected(mutate):
    data = json.loads(_files()[0][PROJECT_MANIFEST_FILENAME])

    with pytest.raises(InvalidProjectManifestError):
        GeneratedProjectManifest.parse(json.dumps(mutate(data)))
    with pytest.raises(InvalidProjectManifestError):
        GeneratedProjectManifest.parse("not json")


def test_artifact_validation_checks_the_manifest_against_the_files_and_dockerfile():
    files, _ = _files()
    assert validate_generated_artifact(files).valid

    data = json.loads(files[PROJECT_MANIFEST_FILENAME])
    stale = {**files, PROJECT_MANIFEST_FILENAME: json.dumps({**data, "artifacts": data["artifacts"][:-1]})}
    wrong_port = {**files, PROJECT_MANIFEST_FILENAME: json.dumps({**data, "configuration": {"base_image": "python:3.11-slim", "port": 1234}})}
    extra_file = {**files, "app/extra.py": "x = 1\n"}
    missing = {k: v for k, v in files.items() if k != PROJECT_MANIFEST_FILENAME}

    assert _categories(stale) == {"MANIFEST_ARTIFACTS"}
    assert _categories(wrong_port) == {"MANIFEST_CONFIGURATION"}
    assert _categories(extra_file) == {"MANIFEST_ARTIFACTS"}
    assert _categories({**files, PROJECT_MANIFEST_FILENAME: "{}"}) == {"INVALID_MANIFEST"}
    assert "MISSING_FILE" in _categories(missing)


def test_validation_detects_an_openapi_file_that_does_not_match_the_app():
    files, _ = _files()

    assert _categories({**files, "openapi.json": "{}\n"}) == {"OPENAPI_FILE_MISMATCH"}
