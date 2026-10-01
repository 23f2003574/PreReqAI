import json

import pytest

from backend.api_generation import (
    CONTRACT_VERSION,
    GENERATOR_ID,
    MARKER_FILENAME,
    METADATA_FILENAME,
    GeneratedProjectMetadata,
    InvalidProjectMetadataError,
    LLMAPIGenerationResult,
    UnsafeOutputDirectoryError,
    validate_generated_artifact,
    write_generated_application,
)
from test_generated_application_entrypoint import _result


def _files():
    result, validated = _result()
    return dict(result.files), validated


def test_metadata_is_created_with_exactly_the_known_identity_fields():
    files, draft = _files()

    data = json.loads(files[METADATA_FILENAME])

    assert data == {
        "contract_version": CONTRACT_VERSION, "draft_id": draft.draft_id, "endpoint": "POST /add",
        "generator": GENERATOR_ID, "project_type": "fastapi-app",
    }


def test_metadata_is_deterministic_and_round_trips():
    files, _ = _files()
    again, _ = _files()

    assert json.loads(files[METADATA_FILENAME]) == json.loads(again[METADATA_FILENAME])
    parsed = GeneratedProjectMetadata.parse(files[METADATA_FILENAME])
    assert parsed.to_json() == files[METADATA_FILENAME] and "time" not in files[METADATA_FILENAME]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: {**d, "generator": "someone.else"},
        lambda d: {**d, "contract_version": 99},
        lambda d: {**d, "contract_version": True},
        lambda d: {**d, "project_type": "django-app"},
        lambda d: {**d, "draft_id": ""},
        lambda d: {k: v for k, v in d.items() if k != "endpoint"},
        lambda d: {**d, "extra": 1},
    ],
)
def test_invalid_metadata_is_rejected_when_parsed(mutate):
    files, _ = _files()

    with pytest.raises(InvalidProjectMetadataError):
        GeneratedProjectMetadata.parse(json.dumps(mutate(json.loads(files[METADATA_FILENAME]))))
    with pytest.raises(InvalidProjectMetadataError):
        GeneratedProjectMetadata.parse("not json")


def test_artifact_validation_requires_and_checks_the_metadata():
    files, _ = _files()
    assert validate_generated_artifact(files).valid

    missing = {k: v for k, v in files.items() if k != METADATA_FILENAME}
    wrong_endpoint = {**files, METADATA_FILENAME: GeneratedProjectMetadata("d", "POST /other").to_json()}
    foreign = {**files, METADATA_FILENAME: '{"generator": "x"}'}

    assert {f["category"] for f in validate_generated_artifact(missing).findings} == {"MISSING_FILE"}
    assert {f["category"] for f in validate_generated_artifact(wrong_endpoint).findings} == {"METADATA_MISMATCH"}
    assert {f["category"] for f in validate_generated_artifact(foreign).findings} == {"INVALID_METADATA"}


def test_metadata_identifies_generated_output_when_the_marker_is_gone(tmp_path):
    files, _ = _files()
    write_generated_application(LLMAPIGenerationResult("d", "POST /add", files), tmp_path)
    (tmp_path / MARKER_FILENAME).unlink()

    write_generated_application(LLMAPIGenerationResult("d", "POST /add", files), tmp_path)  # allowed: proven generated

    assert (tmp_path / MARKER_FILENAME).exists()


def test_an_arbitrary_or_forged_metadata_file_does_not_unlock_overwriting(tmp_path):
    files, _ = _files()
    (tmp_path / "Dockerfile").write_text("the user's own")
    (tmp_path / METADATA_FILENAME).write_text('{"generator": "someone.else"}')

    with pytest.raises(UnsafeOutputDirectoryError):
        write_generated_application(LLMAPIGenerationResult("d", "POST /add", files), tmp_path)
    assert (tmp_path / "Dockerfile").read_text() == "the user's own"
