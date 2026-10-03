import json
from dataclasses import fields
from pathlib import Path

from backend.api_documentation_draft import STATUSES, LLMAPIDocumentationDraft

_STRING_FIELDS = ("draft_id", "endpoint", "summary", "description", "status")
_CONTAINER_FIELDS = {"parameters": dict, "responses": dict, "examples": list}


class InvalidDraftInputError(ValueError):
    """Raised when a draft input file cannot be turned into an
    LLMAPIDocumentationDraft: missing or unsupported file, malformed JSON, or
    fields that are absent, unexpected or of the wrong type."""


def load_draft_file(path) -> LLMAPIDocumentationDraft:
    """Preflight and load the one input the generation workflow accepts: a JSON
    file holding the fields of an LLMAPIDocumentationDraft. Everything is
    checked before any generation work; the schema entries inside
    parameters/responses are left to the generator's own validation. Nothing
    in the file is evaluated."""
    file = Path(path)
    prefix = f"cannot read a draft from {path}: "
    if not file.exists():
        raise InvalidDraftInputError(prefix + "no such file")
    if not file.is_file():
        raise InvalidDraftInputError(prefix + "not a regular file")
    if file.suffix.lower() != ".json":
        raise InvalidDraftInputError(prefix + f"unsupported input type {file.suffix or '(no extension)'!r}; expected a .json file")
    try:
        text = file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise InvalidDraftInputError(prefix + str(error)) from error
    if not text.strip():
        raise InvalidDraftInputError(prefix + "the file is empty")
    try:
        data = json.loads(text)
    except ValueError as error:
        raise InvalidDraftInputError(prefix + f"malformed JSON ({error})") from error
    if not isinstance(data, dict):
        raise InvalidDraftInputError(prefix + "expected a JSON object with the draft's fields")

    expected = {f.name for f in fields(LLMAPIDocumentationDraft)}
    missing, unexpected = sorted(expected - set(data)), sorted(set(data) - expected)
    if missing or unexpected:
        raise InvalidDraftInputError(prefix + "; ".join(
            part for part in (f"missing fields {missing}" if missing else "", f"unexpected fields {unexpected}" if unexpected else "") if part
        ))
    problems = [f"{name} must be a non-empty string" for name in _STRING_FIELDS if not isinstance(data[name], str) or not data[name].strip()]
    problems += [f"{name} must be a {kind.__name__}" for name, kind in _CONTAINER_FIELDS.items() if not isinstance(data[name], kind)]
    if isinstance(data["status"], str) and data["status"] not in STATUSES:
        problems.append(f"status must be one of {sorted(STATUSES)}")
    if problems:
        raise InvalidDraftInputError(prefix + "; ".join(problems))
    return LLMAPIDocumentationDraft(**data)
