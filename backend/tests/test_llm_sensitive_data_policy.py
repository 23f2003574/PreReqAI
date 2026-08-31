import pytest

from backend.llm import LLMRequest, LLMResponse
from backend.llm.sensitive_data_policy import (
    ALLOW,
    BLOCK,
    REDACT,
    LLMSensitiveDataPolicy,
    LLMSensitiveDataPolicyService,
    UnknownDataTypeError,
)

SK_KEY = "sk- style API key"
AWS_KEY = "AWS access key"
BEARER = "bearer token"
CREDENTIAL_ASSIGNMENT = "credential assignment"

SECRET = "sk-abcdefghijklmnopqrstuvwxyz123456"
AWS_SECRET = "AKIAABCDEFGHIJKLMNOP"
BEARER_TOKEN = "Authorization: Bearer abc123.def456-ghi789"


def build_service():
    return LLMSensitiveDataPolicyService()


def test_allowed_data_is_allowed():
    service = build_service()
    service.register(LLMSensitiveDataPolicy(policy_id="p1", data_type=SK_KEY, action=ALLOW))

    value = f"here is your key: {SECRET}"

    assert service.evaluate(value) == ALLOW
    assert service.allowed(value) is True
    assert service.evaluate("just an ordinary sentence") == ALLOW


def test_redacted_data_action():
    service = build_service()
    service.register(LLMSensitiveDataPolicy(policy_id="p1", data_type=BEARER, action=REDACT))

    assert service.evaluate(BEARER_TOKEN) == REDACT
    assert service.allowed(BEARER_TOKEN) is True


def test_blocked_data_action():
    service = build_service()
    service.register(LLMSensitiveDataPolicy(policy_id="p1", data_type=AWS_KEY, action=BLOCK))

    value = f"aws={AWS_SECRET}"

    assert service.evaluate(value) == BLOCK
    assert service.allowed(value) is False


def test_policy_precedence_block_overrides_redact():
    service = build_service()
    service.register(LLMSensitiveDataPolicy(policy_id="p1", data_type=SK_KEY, action=REDACT))
    service.register(LLMSensitiveDataPolicy(policy_id="p2", data_type=AWS_KEY, action=BLOCK))

    value = f"openai={SECRET} aws={AWS_SECRET}"

    assert service.evaluate(value) == BLOCK
    assert service.allowed(value) is False


def test_unknown_data_type_does_not_silently_allow():
    service = build_service()

    with pytest.raises(UnknownDataTypeError):
        service.get(CREDENTIAL_ASSIGNMENT)

    value = "password=hunter2"

    assert service.evaluate(value) == BLOCK
    assert service.allowed(value) is False


def test_input_integration_evaluates_an_llm_request():
    service = build_service()
    service.register(LLMSensitiveDataPolicy(policy_id="p1", data_type=SK_KEY, action=BLOCK))

    unsafe_request = LLMRequest(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"please use this key: {SECRET}"}],
    )
    safe_request = LLMRequest(
        model="gpt-4o",
        messages=[{"role": "user", "content": "what's the weather like?"}],
    )

    assert service.evaluate(unsafe_request) == BLOCK
    assert service.allowed(unsafe_request) is False
    assert service.evaluate(safe_request) == ALLOW
    assert service.allowed(safe_request) is True


def test_output_integration_evaluates_an_llm_response():
    service = build_service()
    service.register(LLMSensitiveDataPolicy(policy_id="p1", data_type=BEARER, action=REDACT))

    unsafe_response = LLMResponse(content=BEARER_TOKEN, model="gpt-4o", usage={})
    safe_response = LLMResponse(content="here is a summary", model="gpt-4o", usage={})

    assert service.evaluate(unsafe_response) == REDACT
    assert service.allowed(unsafe_response) is True
    assert service.evaluate(safe_response) == ALLOW
