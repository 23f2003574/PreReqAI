import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_regression import LLMCodePatchRegressionService
from backend.code_patch_security_review import (
    LLMCodePatchSecurityService,
    MalformedSecurityResponseError,
    UnverifiedPatchError,
)
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
    return (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        regression_service,
        security_service,
        provider,
    )


EMPTY_REVIEW_FINDINGS = json.dumps({"findings": [], "confidence": 1.0})
EMPTY_VALIDATION_FINDINGS = json.dumps({"findings": []})
EMPTY_SECURITY_FINDINGS = json.dumps({"findings": []})

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


def build_reviewed_execution(operation_response, output, security_script, job_id="job-1"):
    """A real end-to-end pipeline through Commit #1-#7, leaving
    `security_script` scripted responses queued for the caller's own
    LLMCodePatchSecurityService.analyze() call."""
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),  # Commit #6's own re-review
            make_response(EMPTY_REVIEW_FINDINGS),  # Commit #7's own re-review
            *[make_response(r) for r in security_script],
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

    return services, generated_output, execution


def test_security_finding_from_patched_output():
    services, generated_output, execution = build_reviewed_execution(
        INEFFECTIVE_OPERATION_RESPONSE, {"source": LEAKY_SOURCE}, [EMPTY_SECURITY_FINDINGS]
    )
    security_service = services[7]

    findings = security_service.analyze(execution.execution_id)

    assert any(finding.category == "SECRETS" and finding.severity == "CRITICAL" for finding in findings)
    assert security_service.findings(execution.execution_id) == findings


def test_secret_redaction():
    services, generated_output, execution = build_reviewed_execution(
        INEFFECTIVE_OPERATION_RESPONSE, {"source": LEAKY_SOURCE}, [EMPTY_SECURITY_FINDINGS]
    )
    security_service = services[7]

    findings = security_service.analyze(execution.execution_id)

    secrets_findings = [f for f in findings if f.category == "SECRETS"]
    assert secrets_findings
    for finding in findings:
        assert "sk-abcdefghijklmnop" not in finding.evidence


def test_critical_filtering():
    services, generated_output, execution = build_reviewed_execution(
        INEFFECTIVE_OPERATION_RESPONSE, {"source": LEAKY_SOURCE}, [EMPTY_SECURITY_FINDINGS]
    )
    security_service = services[7]
    security_service.analyze(execution.execution_id)

    assert security_service.blocking(execution.execution_id) is True


def test_critical_filtering_excludes_non_critical_findings():
    output = {"source": LEAKY_SOURCE, "endpoints": [{"path": "/add", "method": "GET"}]}
    services, generated_output, execution = build_reviewed_execution(
        GOOD_OPERATION_RESPONSE, output, [EMPTY_SECURITY_FINDINGS]
    )
    security_service = services[7]

    findings = security_service.analyze(execution.execution_id)

    assert any(finding.category == "AUTH" for finding in findings)
    assert all(finding.severity != "CRITICAL" for finding in findings)
    assert security_service.blocking(execution.execution_id) is False


def test_patched_output_integration():
    output = {"source": LEAKY_SOURCE, "endpoints": [{"path": "/add", "method": "POST"}]}
    services, generated_output, execution = build_reviewed_execution(
        GOOD_OPERATION_RESPONSE, output, [EMPTY_SECURITY_FINDINGS]
    )
    security_service = services[7]

    findings = security_service.analyze(execution.execution_id)

    # The patch removed the credential -- no SECRETS finding should remain --
    # but the endpoints structure (untouched by the patch) still yields a
    # real AUTH finding grounded in the actual, current generated output.
    assert generated_output.output["source"] == CLEAN_SOURCE
    assert not any(finding.category == "SECRETS" for finding in findings)
    auth_findings = [f for f in findings if f.category == "AUTH"]
    assert auth_findings
    assert auth_findings[0].severity == "ERROR"


@pytest.mark.parametrize(
    "malformed_response",
    [
        "not json",
        json.dumps({"findings": "not-a-list"}),
        json.dumps({"findings": [{"category": "NOT_REAL", "severity": "INFO", "evidence": "x", "confidence": 0.5}]}),
        json.dumps({"findings": [{"category": "AUTH", "severity": "NOT_REAL", "evidence": "x", "confidence": 0.5}]}),
    ],
)
def test_category_severity_validation(malformed_response):
    services, generated_output, execution = build_reviewed_execution(
        GOOD_OPERATION_RESPONSE, {"source": LEAKY_SOURCE}, [malformed_response]
    )
    security_service = services[7]

    with pytest.raises(MalformedSecurityResponseError):
        security_service.analyze(execution.execution_id)


@pytest.mark.parametrize(
    "malformed_response",
    [
        json.dumps({"findings": [{"category": "AUTH", "severity": "INFO", "evidence": "", "confidence": 0.5}]}),
        json.dumps({"findings": [{"category": "AUTH", "severity": "INFO", "evidence": "x", "confidence": 2.0}]}),
    ],
)
def test_malformed_llm_response(malformed_response):
    services, generated_output, execution = build_reviewed_execution(
        GOOD_OPERATION_RESPONSE, {"source": LEAKY_SOURCE}, [malformed_response]
    )
    security_service = services[7]

    with pytest.raises(MalformedSecurityResponseError):
        security_service.analyze(execution.execution_id)


def test_unverified_patch_is_rejected():
    services, generated_output, execution = build_reviewed_execution(
        GOOD_OPERATION_RESPONSE, {"source": LEAKY_SOURCE}, [EMPTY_SECURITY_FINDINGS]
    )
    security_service = services[7]
    generated_output.output["source"] = "def broken(:\n    pass"
    verification_service = services[5]
    verification_service.verify(execution.execution_id)

    with pytest.raises(UnverifiedPatchError):
        security_service.analyze(execution.execution_id)
