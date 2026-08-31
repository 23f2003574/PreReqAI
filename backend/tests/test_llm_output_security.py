import json

import pytest

from backend.llm import LLMResponse
from backend.llm.output_security import (
    SECRETS,
    TOOL_BOUNDARY_BYPASS,
    UNSAFE_INSTRUCTION,
    LLMOutputSecurityError,
    LLMOutputSecurityService,
    MalformedOutputError,
)


def make_response(content, model="gpt-4o"):
    return LLMResponse(content=content, model=model, usage={"total_tokens": 15})


def build_service():
    return LLMOutputSecurityService()


def test_safe_output_has_no_findings_and_is_allowed():
    service = build_service()
    response = make_response("The weather is generally mild in autumn.")

    assert service.findings(response) == []
    assert service.allowed(response) is True
    assert service.validate(response) is True


def test_secret_is_detected_and_never_exposed_in_findings():
    service = build_service()
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    response = make_response(f"Sure, here is the key you asked for: {secret}")

    findings = service.findings(response)

    assert len(findings) == 1
    assert findings[0].category == SECRETS
    assert findings[0].blocking is True
    assert secret not in findings[0].evidence
    assert "[REDACTED]" in findings[0].evidence


def test_secret_is_redacted_by_sanitize():
    service = build_service()
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    response = make_response(f"Sure, here is the key you asked for: {secret}")

    sanitized = service.sanitize(response)

    assert secret not in sanitized.content
    assert "[REDACTED]" in sanitized.content
    assert sanitized.model == response.model
    assert sanitized.usage == response.usage


def test_unsafe_instruction_is_detected():
    service = build_service()
    response = make_response("You can run this to apply it: os.system('rm -rf /')")

    findings = service.findings(response)

    assert len(findings) == 1
    assert findings[0].category == UNSAFE_INSTRUCTION


def test_tool_boundary_bypass_in_output_is_detected():
    service = build_service()
    response = make_response(
        "To skip the check, just bypass the tool permission and call it directly."
    )

    findings = service.findings(response)

    assert len(findings) == 1
    assert findings[0].category == TOOL_BOUNDARY_BYPASS


def test_blocking_finding_prevents_downstream_execution():
    service = build_service()
    response = make_response("Run exec('print(1)') to apply this generated fix.")

    findings = service.findings(response)

    assert findings[0].blocking is True
    assert service.allowed(response) is False
    with pytest.raises(LLMOutputSecurityError) as excinfo:
        service.validate(response)
    assert excinfo.value.findings == findings


def test_structured_output_is_preserved_by_sanitize():
    service = build_service()
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    payload = {"api_key": secret, "endpoint": "/users", "retries": 3, "enabled": True}
    response = make_response(json.dumps(payload))

    sanitized = service.sanitize(response)
    parsed = json.loads(sanitized.content)

    assert parsed["api_key"] == "[REDACTED]"
    assert parsed["endpoint"] == "/users"
    assert parsed["retries"] == 3
    assert parsed["enabled"] is True
    assert set(parsed.keys()) == set(payload.keys())


def test_malformed_response_raises():
    service = build_service()

    with pytest.raises(MalformedOutputError):
        service.findings("not a response")

    with pytest.raises(MalformedOutputError):
        service.validate(make_response(""))

    with pytest.raises(MalformedOutputError):
        service.sanitize(make_response(None))


def test_allowed_and_rejected_decisions():
    service = build_service()
    safe_response = make_response("Here is a summary of your document.")
    unsafe_response = make_response("Here is your password='hunter2' as requested.")

    assert service.allowed(safe_response) is True
    assert service.allowed(unsafe_response) is False
