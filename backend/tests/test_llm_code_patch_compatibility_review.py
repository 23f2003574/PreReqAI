import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_compatibility_review import (
    LLMCodePatchCompatibilityService,
    MalformedCompatibilityResponseError,
    UnverifiedPatchError,
)
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_regression import LLMCodePatchRegressionService
from backend.code_patch_security_review import LLMCodePatchSecurityService
from backend.code_patch_validation import LLMCodePatchValidationService
from backend.code_patch_verification import LLMCodePatchVerificationService
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
    regression_service = LLMCodePatchRegressionService(
        verification_service, execution_service, patch_service, fix_service, review_service
    )
    security_service = LLMCodePatchSecurityService(
        verification_service,
        regression_service,
        execution_service,
        patch_service,
        fix_service,
        review_service,
        orchestration_service,
        context_service,
    )
    compatibility_service = LLMCodePatchCompatibilityService(
        verification_service,
        regression_service,
        security_service,
        execution_service,
        patch_service,
        fix_service,
        review_service,
        orchestration_service,
        context_service,
    )
    return (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        regression_service,
        security_service,
        compatibility_service,
        provider,
    )


EMPTY_REVIEW_FINDINGS = json.dumps({"findings": [], "confidence": 1.0})
EMPTY_VALIDATION_FINDINGS = json.dumps({"findings": []})
EMPTY_SECURITY_FINDINGS = json.dumps({"findings": []})
EMPTY_COMPATIBILITY_FINDINGS = json.dumps({"findings": [], "confidence": 1.0})

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
DEPENDENCY_SOURCE = "def add(a, b):\n    os.system('rm -rf /')\n    return a + b"


def operation_response(value: str) -> str:
    return json.dumps(
        {
            "operations": [{"op": "REPLACE", "location": "source", "value": value}],
            "rationale": "Replace the source per the fix suggestion.",
        }
    )


NEW_COMPATIBILITY_FINDING_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "category": "COMPATIBILITY",
                "location": "source",
                "severity": "CRITICAL",
                "message": "the replacement signature is incompatible with existing callers",
            }
        ],
        "confidence": 0.8,
    }
)


def build_reviewed_execution(
    output,
    operation_value,
    verify_review_response=EMPTY_REVIEW_FINDINGS,
    regression_review_response=EMPTY_REVIEW_FINDINGS,
    security_response=EMPTY_SECURITY_FINDINGS,
    job_id="job-1",
):
    """A real end-to-end pipeline through Commit #1-#8, leaving one
    scripted response queued for the caller's own
    LLMCodePatchCompatibilityService.review() call."""

    def build_and_run(compatibility_response):
        services = build_services(
            [
                make_response(EMPTY_REVIEW_FINDINGS),
                make_response(ONE_SUGGESTION_RESPONSE),
                make_response(operation_response(operation_value)),
                make_response(EMPTY_VALIDATION_FINDINGS),
                make_response(verify_review_response),
                make_response(regression_review_response),
                make_response(security_response),
                make_response(compatibility_response),
            ]
        )
        (
            review_service,
            fix_service,
            patch_service,
            validation_service,
            execution_service,
            verification_service,
            regression_service,
            security_service,
            compatibility_service,
            provider,
        ) = services

        generated_output = CompilerJobResult(job_id=job_id, status="SUCCEEDED", output=output)
        review = review_service.review(generated_output)
        suggestion = fix_service.suggest(review.review_id)[0]
        plan = patch_service.plan(suggestion.suggestion_id)
        validation_service.validate(plan.plan_id)
        execution = execution_service.apply(plan.plan_id)
        verification_service.verify(execution.execution_id)
        regression_service.analyze(execution.execution_id)
        security_service.analyze(execution.execution_id)

        return services, generated_output, execution

    return build_and_run


def test_compatible_patch():
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    services, generated_output, execution = build_and_run(EMPTY_COMPATIBILITY_FINDINGS)
    compatibility_service = services[8]

    review = compatibility_service.review(execution.execution_id)

    assert review.execution_id == execution.execution_id
    assert review.compatible is True
    assert review.findings == []
    assert compatibility_service.compatible(execution.execution_id) is True


def test_unsupported_structure():
    output = {"source": LEAKY_SOURCE, "endpoints": [{"path": "add", "method": "FETCH"}]}
    build_and_run = build_reviewed_execution(output, CLEAN_SOURCE)
    services, generated_output, execution = build_and_run(EMPTY_COMPATIBILITY_FINDINGS)
    compatibility_service = services[8]

    review = compatibility_service.review(execution.execution_id)

    assert review.compatible is False
    categories = {finding["category"] for finding in review.findings}
    assert "UNSUPPORTED_METHOD" in categories
    assert "UNSUPPORTED_ENDPOINT_PATTERN" in categories


def test_schema_incompatibility_from_regression():
    build_and_run = build_reviewed_execution(
        {"source": LEAKY_SOURCE},
        CLEAN_SOURCE,
        regression_review_response=NEW_COMPATIBILITY_FINDING_RESPONSE,
    )
    services, generated_output, execution = build_and_run(EMPTY_COMPATIBILITY_FINDINGS)
    compatibility_service = services[8]

    review = compatibility_service.review(execution.execution_id)

    assert review.compatible is False
    assert any(finding["category"] == "SCHEMA_INCOMPATIBILITY" for finding in review.findings)


def test_import_incompatibility_from_security_review():
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, DEPENDENCY_SOURCE)
    services, generated_output, execution = build_and_run(EMPTY_COMPATIBILITY_FINDINGS)
    compatibility_service = services[8]

    review = compatibility_service.review(execution.execution_id)

    assert review.compatible is False
    assert any(finding["category"] == "IMPORT_INCOMPATIBILITY" for finding in review.findings)


def test_blocking_finding_from_llm_response():
    llm_blocking_response = json.dumps(
        {
            "findings": [
                {
                    "category": "GENERATED_STRUCTURE",
                    "message": "the generated output no longer matches a compilable shape",
                    "blocking": True,
                }
            ],
            "confidence": 0.6,
        }
    )
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    services, generated_output, execution = build_and_run(llm_blocking_response)
    compatibility_service = services[8]

    review = compatibility_service.review(execution.execution_id)

    assert review.compatible is False
    assert compatibility_service.compatible(execution.execution_id) is False


@pytest.mark.parametrize(
    "malformed_response",
    [
        "not json",
        json.dumps({"findings": []}),
        json.dumps({"findings": [{"category": "NOT_REAL", "message": "x", "blocking": True}], "confidence": 0.5}),
        json.dumps({"findings": [{"category": "GENERATED_STRUCTURE", "message": "", "blocking": True}], "confidence": 0.5}),
        json.dumps({"findings": [], "confidence": 2.0}),
    ],
)
def test_malformed_response(malformed_response):
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    services, generated_output, execution = build_and_run(malformed_response)
    compatibility_service = services[8]

    with pytest.raises(MalformedCompatibilityResponseError):
        compatibility_service.review(execution.execution_id)


def test_compiler_integration_with_supported_route():
    output = {"source": LEAKY_SOURCE, "endpoints": [{"path": "/add", "method": "POST"}]}
    build_and_run = build_reviewed_execution(output, CLEAN_SOURCE)
    services, generated_output, execution = build_and_run(EMPTY_COMPATIBILITY_FINDINGS)
    compatibility_service = services[8]

    review = compatibility_service.review(execution.execution_id)

    assert review.compatible is True
    assert review.findings == []


def test_unverified_patch_is_rejected():
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    services, generated_output, execution = build_and_run(EMPTY_COMPATIBILITY_FINDINGS)
    compatibility_service = services[8]
    verification_service = services[5]
    generated_output.output["source"] = "def broken(:\n    pass"
    verification_service.verify(execution.execution_id)

    with pytest.raises(UnverifiedPatchError):
        compatibility_service.review(execution.execution_id)
