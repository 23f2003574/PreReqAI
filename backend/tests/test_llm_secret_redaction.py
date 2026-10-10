import json

from backend.llm import LLMResponse
from backend.llm.output_security import LLMOutputSecurityService
from backend.llm.secret_redaction import LLMSecretRedactionService


def build_service():
    return LLMSecretRedactionService()


def test_token_is_detected():
    service = build_service()

    matches = service.detect("Authorization: Bearer abc123.def456-ghi789")

    assert len(matches) == 1
    assert matches[0]["location"] == "$"
    assert "bearer" in matches[0]["pattern"].lower()
    assert service.contains_secret("Authorization: Bearer abc123.def456-ghi789") is True


def test_credential_assignment_is_detected():
    service = build_service()

    matches = service.detect("password=hunter2")

    assert len(matches) == 1
    assert "credential" in matches[0]["pattern"].lower()
    assert service.contains_secret("password=hunter2") is True


def test_redaction_never_returns_the_secret():
    service = build_service()
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"

    redacted = service.redact(f"here is your key: {secret}")

    assert secret not in redacted
    assert "[REDACTED]" in redacted


def test_multiple_secrets_are_all_detected_and_redacted():
    service = build_service()
    aws_key = "AKIAABCDEFGHIJKLMNOP"
    api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
    text = f"aws={aws_key} and openai={api_key}"

    matches = service.detect(text)
    redacted = service.redact(text)

    assert len(matches) >= 2
    assert aws_key not in redacted
    assert api_key not in redacted


def test_secrets_are_detected_and_redacted_in_a_structured_payload():
    service = build_service()
    secret = "AKIAABCDEFGHIJKLMNOP"
    payload = {
        "headers": {"Authorization": f"Bearer {secret}"},
        "body": {"count": 2, "enabled": True, "tags": ["a", "b"]},
    }

    matches = service.detect(payload)
    redacted = service.redact(payload)

    assert any(match["location"] == "headers.Authorization" for match in matches)
    assert secret not in redacted["headers"]["Authorization"]
    assert redacted["body"] == {"count": 2, "enabled": True, "tags": ["a", "b"]}
    assert set(redacted.keys()) == {"headers", "body"}


def test_ordinary_values_are_not_false_positives():
    service = build_service()
    payload = {
        "name": "Alice",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "count": 42,
        "note": "This is a perfectly ordinary sentence about the weather.",
    }

    assert service.contains_secret(payload) is False
    assert service.detect(payload) == []
    assert service.redact(payload) == payload


def test_already_redacted_value_is_unchanged():
    service = build_service()

    once = service.redact("api_key=sk-abcdefghijklmnopqrstuvwxyz123456")
    twice = service.redact(once)

    assert once == twice
    assert service.contains_secret(once) is False


def test_output_security_service_reuses_secret_redaction_for_secrets_and_structure():
    output_service = LLMOutputSecurityService()
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"

    response = LLMResponse(
        content=json.dumps({"api_key": secret, "retries": 3}),
        model="gpt-4o",
        usage={},
    )

    sanitized = output_service.sanitize(response)
    parsed = json.loads(sanitized.content)

    assert parsed["api_key"] == "[REDACTED]"
    assert parsed["retries"] == 3
