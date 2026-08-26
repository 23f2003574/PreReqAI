import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import LLMCodePatchExecutionService, UnknownExecutionError
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_validation import LLMCodePatchValidationService
from backend.code_patch_verification import (
    ExecutionNotAppliedError,
    LLMCodePatchVerificationService,
    UnknownPatchVerificationError,
)
from backend.compilation_execution import CompilerJobResult
from backend.generated_code_review import LLMGeneratedCodeReviewService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays one scripted outcome per call, in order."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


def build_services(script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    provider = ScriptedProvider(script)
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": provider},
    )

    review_service = LLMGeneratedCodeReviewService(orchestration_service, context_service)
    fix_service = LLMCodeFixSuggestionService(review_service, orchestration_service, context_service)
    patch_service = LLMCodePatchService(review_service, fix_service, orchestration_service, context_service)
    validation_service = LLMCodePatchValidationService(fix_service, patch_service, orchestration_service, context_service)
    execution_service = LLMCodePatchExecutionService(review_service, fix_service, patch_service, validation_service)
    verification_service = LLMCodePatchVerificationService(execution_service, review_service, fix_service, patch_service)
    return review_service, fix_service, patch_service, validation_service, execution_service, verification_service, provider


EMPTY_REVIEW_FINDINGS = json.dumps({"findings": [], "confidence": 1.0})
EMPTY_VALIDATION_FINDINGS = json.dumps({"findings": []})

ONE_SUGGESTION_RESPONSE = json.dumps(
    {
        "suggestions": [
            {
                "finding_index": 0,
                "change": "Remove the hardcoded credential from the generated source.",
                "rationale": "A hardcoded secret must never ship in generated code.",
                "confidence": 0.9,
                "risk": "LOW",
            }
        ]
    }
)

CLEAN_SOURCE = "def add(a, b):\n    return a + b"
LEAKY_SOURCE = "def add(a, b):\n    api_key = 'sk-abcdefghijklmnop'\n    return a + b"

GOOD_OPERATION_RESPONSE = json.dumps(
    {
        "operations": [{"op": "REPLACE", "location": "source", "value": CLEAN_SOURCE}],
        "rationale": "Replace the leaking source with a version that has no hardcoded credential.",
    }
)

INEFFECTIVE_OPERATION_RESPONSE = json.dumps(
    {
        "operations": [{"op": "REPLACE", "location": "source", "value": LEAKY_SOURCE}],
        "rationale": "A no-op fix that leaves the credential in place.",
    }
)


def build_applied_execution(operation_response, job_id="job-1"):
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        provider,
    ) = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    generated_output = CompilerJobResult(job_id=job_id, status="SUCCEEDED", output={"source": LEAKY_SOURCE})
    review = review_service.review(generated_output)
    suggestion = fix_service.suggest(review.review_id)[0]
    plan = patch_service.plan(suggestion.suggestion_id)
    validation_service.validate(plan.plan_id)
    execution = execution_service.apply(plan.plan_id)
    assert execution.status == "SUCCEEDED"

    return (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        provider,
        generated_output,
        execution,
    )


def test_successful_verification():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        provider,
        generated_output,
        execution,
    ) = build_applied_execution(GOOD_OPERATION_RESPONSE)
    provider._script.append(make_response(EMPTY_REVIEW_FINDINGS))  # the re-review's own LLM call

    verification = verification_service.verify(execution.execution_id)

    assert verification.execution_id == execution.execution_id
    assert verification.syntax_valid is True
    assert verification.tests_passed is True
    assert verification.findings == []
    assert verification_service.blocking(execution.execution_id) is False


def test_test_failure_when_original_problem_still_reproduces():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        provider,
        generated_output,
        execution,
    ) = build_applied_execution(INEFFECTIVE_OPERATION_RESPONSE)
    provider._script.append(make_response(EMPTY_REVIEW_FINDINGS))  # the re-review's own LLM call

    verification = verification_service.verify(execution.execution_id)

    assert verification.syntax_valid is True
    assert verification.tests_passed is False
    assert any(finding["category"] == "TEST_FAILURE" for finding in verification.findings)
    assert verification_service.blocking(execution.execution_id) is True


def test_syntax_failure_skips_tests():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        provider,
        generated_output,
        execution,
    ) = build_applied_execution(GOOD_OPERATION_RESPONSE)
    # Simulate the generated output being corrupted after application --
    # verify() must catch this deterministically, before ever re-reviewing.
    generated_output.output["source"] = "def broken(:\n    pass"

    verification = verification_service.verify(execution.execution_id)

    assert verification.syntax_valid is False
    assert verification.tests_passed is False
    assert any(finding["category"] == "SYNTAX_ERROR" for finding in verification.findings)
    assert any(finding["category"] == "TESTS_SKIPPED" for finding in verification.findings)
    assert verification_service.blocking(execution.execution_id) is True
    assert provider.calls == 4  # no extra LLM call was made for the skipped re-review


def test_invalid_execution_never_applied():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        provider,
        generated_output,
        execution,
    ) = build_applied_execution(GOOD_OPERATION_RESPONSE)
    execution_service.rollback(execution.execution_id)

    with pytest.raises(ExecutionNotAppliedError):
        verification_service.verify(execution.execution_id)


def test_invalid_execution_unknown_id_propagates_commit5_error():
    review_service, fix_service, patch_service, validation_service, execution_service, verification_service, provider = (
        build_services([make_response(EMPTY_REVIEW_FINDINGS)])
    )

    with pytest.raises(UnknownExecutionError):
        verification_service.verify("no-such-execution")


def test_verification_state():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        provider,
        generated_output,
        execution,
    ) = build_applied_execution(GOOD_OPERATION_RESPONSE)

    with pytest.raises(UnknownPatchVerificationError):
        verification_service.findings(execution.execution_id)
    with pytest.raises(UnknownPatchVerificationError):
        verification_service.blocking(execution.execution_id)

    provider._script.append(make_response(EMPTY_REVIEW_FINDINGS))
    verification = verification_service.verify(execution.execution_id)

    assert verification_service.findings(execution.execution_id) == verification.findings
    assert verification_service.blocking(execution.execution_id) is False
