import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_compatibility_review import LLMCodePatchCompatibilityService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_quality_review import (
    LLMCodePatchQualityService,
    MalformedQualityResponseError,
    UnverifiedPatchError,
)
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
    quality_service = LLMCodePatchQualityService(
        verification_service,
        regression_service,
        security_service,
        compatibility_service,
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
        quality_service,
        provider,
    )


EMPTY_REVIEW_FINDINGS = json.dumps({"findings": [], "confidence": 1.0})
EMPTY_VALIDATION_FINDINGS = json.dumps({"findings": []})
EMPTY_SECURITY_FINDINGS = json.dumps({"findings": []})
EMPTY_COMPATIBILITY_FINDINGS = json.dumps({"findings": [], "confidence": 1.0})
EMPTY_QUALITY_FINDINGS = json.dumps({"findings": []})

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

LEAKY_SOURCE = "def add(a, b):\n    api_key = 'sk-abcdefghijklmnop'\n    return a + b"
BAD_STYLE_SOURCE = "def AddNumbers(a, b):\n    return a + b"

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


def operation_response(value: str) -> str:
    return json.dumps(
        {
            "operations": [{"op": "REPLACE", "location": "source", "value": value}],
            "rationale": "Replace the source per the fix suggestion.",
        }
    )


def build_reviewed_execution(
    output,
    operation_value,
    regression_review_response=EMPTY_REVIEW_FINDINGS,
    security_response=EMPTY_SECURITY_FINDINGS,
    compatibility_response=EMPTY_COMPATIBILITY_FINDINGS,
    job_id="job-1",
):
    def build_and_run(quality_response):
        services = build_services(
            [
                make_response(EMPTY_REVIEW_FINDINGS),
                make_response(ONE_SUGGESTION_RESPONSE),
                make_response(operation_response(operation_value)),
                make_response(EMPTY_VALIDATION_FINDINGS),
                make_response(EMPTY_REVIEW_FINDINGS),  # Commit #6's own re-review
                make_response(regression_review_response),  # Commit #7's own re-review
                make_response(security_response),
                make_response(compatibility_response),
                make_response(quality_response),
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
            quality_service,
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
        compatibility_service.review(execution.execution_id)

        return services, generated_output, execution

    return build_and_run


def test_quality_finding_from_patched_output():
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, BAD_STYLE_SOURCE)
    services, generated_output, execution = build_and_run(EMPTY_QUALITY_FINDINGS)
    quality_service = services[9]

    findings = quality_service.analyze(execution.execution_id)

    assert any(f.category == "STYLE" and "AddNumbers" in f.evidence for f in findings)
    assert any(f.category == "MAINTAINABILITY" and "no docstring" in f.evidence for f in findings)
    assert quality_service.findings(execution.execution_id) == findings


@pytest.mark.parametrize(
    "malformed_response",
    [
        json.dumps(
            {"findings": [{"category": "NOT_REAL", "severity": "INFO", "location": "source", "evidence": "x", "confidence": 0.5}]}
        ),
        json.dumps(
            {"findings": [{"category": "STYLE", "severity": "NOT_REAL", "location": "source", "evidence": "x", "confidence": 0.5}]}
        ),
    ],
)
def test_category_severity_validation(malformed_response):
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, BAD_STYLE_SOURCE)
    services, generated_output, execution = build_and_run(malformed_response)
    quality_service = services[9]

    with pytest.raises(MalformedQualityResponseError):
        quality_service.analyze(execution.execution_id)


@pytest.mark.parametrize(
    "malformed_response",
    [
        json.dumps(
            {"findings": [{"category": "STYLE", "severity": "INFO", "location": "not-a-real-key", "evidence": "x", "confidence": 0.5}]}
        ),
        json.dumps(
            {"findings": [{"category": "STYLE", "severity": "INFO", "location": "source", "evidence": "", "confidence": 0.5}]}
        ),
    ],
)
def test_evidence_validation(malformed_response):
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, BAD_STYLE_SOURCE)
    services, generated_output, execution = build_and_run(malformed_response)
    quality_service = services[9]

    with pytest.raises(MalformedQualityResponseError):
        quality_service.analyze(execution.execution_id)


def test_critical_filtering():
    build_and_run = build_reviewed_execution(
        {"source": LEAKY_SOURCE},
        "def add(a, b):\n    return a + b",
        regression_review_response=NEW_COMPATIBILITY_FINDING_RESPONSE,
    )
    services, generated_output, execution = build_and_run(EMPTY_QUALITY_FINDINGS)
    quality_service = services[9]

    findings = quality_service.analyze(execution.execution_id)

    assert any(f.severity == "CRITICAL" and f.category == "MAINTAINABILITY" for f in findings)
    assert quality_service.blocking(execution.execution_id) is True


def test_critical_filtering_excludes_warning_only_findings():
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, BAD_STYLE_SOURCE)
    services, generated_output, execution = build_and_run(EMPTY_QUALITY_FINDINGS)
    quality_service = services[9]

    findings = quality_service.analyze(execution.execution_id)

    assert all(f.severity != "CRITICAL" for f in findings)
    assert quality_service.blocking(execution.execution_id) is False


@pytest.mark.parametrize(
    "malformed_response",
    [
        "not json",
        json.dumps({"findings": "not-a-list"}),
        json.dumps({"findings": [{"category": "STYLE", "severity": "INFO", "location": "source"}]}),
    ],
)
def test_malformed_llm_response(malformed_response):
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, BAD_STYLE_SOURCE)
    services, generated_output, execution = build_and_run(malformed_response)
    quality_service = services[9]

    with pytest.raises(MalformedQualityResponseError):
        quality_service.analyze(execution.execution_id)


def test_patched_output_integration():
    build_and_run = build_reviewed_execution(
        {"source": LEAKY_SOURCE},
        BAD_STYLE_SOURCE,
        security_response=EMPTY_SECURITY_FINDINGS,
    )
    services, generated_output, execution = build_and_run(EMPTY_QUALITY_FINDINGS)
    quality_service = services[9]
    security_service = services[7]

    findings = quality_service.analyze(execution.execution_id)

    # The current, live output (post-patch) drives the deterministic checks
    # directly -- and Commit #8's own already-computed security findings
    # (the still-present secret was replaced, but the SECRETS finding from
    # the *pre*-patch source no longer applies since the fix succeeded)
    # are folded straight through as MAINTAINABILITY evidence.
    assert generated_output.output["source"] == BAD_STYLE_SOURCE
    assert any(f.category == "STYLE" for f in findings)
    security_findings = security_service.findings(execution.execution_id)
    maintainability_from_security = [
        f for f in findings if f.category == "MAINTAINABILITY" and "security review flagged" in f.evidence
    ]
    assert len(maintainability_from_security) == len(security_findings)


def test_unverified_patch_is_rejected():
    build_and_run = build_reviewed_execution({"source": LEAKY_SOURCE}, "def add(a, b):\n    return a + b")
    services, generated_output, execution = build_and_run(EMPTY_QUALITY_FINDINGS)
    quality_service = services[9]
    verification_service = services[5]
    generated_output.output["source"] = "def broken(:\n    pass"
    verification_service.verify(execution.execution_id)

    with pytest.raises(UnverifiedPatchError):
        quality_service.analyze(execution.execution_id)
