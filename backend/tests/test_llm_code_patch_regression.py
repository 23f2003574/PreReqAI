import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_regression import (
    LLMCodePatchRegressionService,
    MissingBaselineError,
    UnknownRegressionAnalysisError,
    UnverifiedPatchError,
)
from backend.code_patch_validation import LLMCodePatchValidationService
from backend.code_patch_verification import LLMCodePatchVerificationService, UnknownPatchVerificationError
from backend.compilation_execution import CompilerJobResult
from backend.generated_code_review import CATEGORIES, LLMGeneratedCodeReviewService
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
    return (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        verification_service,
        regression_service,
        provider,
    )


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


def new_compatibility_finding_response():
    return json.dumps(
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


def new_quality_finding_response():
    return json.dumps(
        {
            "findings": [
                {
                    "category": "QUALITY",
                    "location": "source",
                    "severity": "WARNING",
                    "message": "the replacement function has no docstring",
                }
            ],
            "confidence": 0.7,
        }
    )


def build_verified_execution(post_apply_reviews, job_id="job-1"):
    """A real end-to-end pipeline through Commit #1 review, #2 suggestion,
    #3 plan, #4 validation, #5 application, and #6 verification -- leaving
    exactly `post_apply_reviews` scripted responses queued for whatever the
    caller does next (Commit #7's own re-review call)."""
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(GOOD_OPERATION_RESPONSE),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),  # Commit #6's own re-review
            *[make_response(r) for r in post_apply_reviews],
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
        provider,
    ) = services

    generated_output = CompilerJobResult(job_id=job_id, status="SUCCEEDED", output={"source": LEAKY_SOURCE})
    review = review_service.review(generated_output)
    suggestion = fix_service.suggest(review.review_id)[0]
    plan = patch_service.plan(suggestion.suggestion_id)
    validation_service.validate(plan.plan_id)
    execution = execution_service.apply(plan.plan_id)
    verification = verification_service.verify(execution.execution_id)
    assert verification.syntax_valid is True

    return services, generated_output, execution


def test_no_regression():
    services, generated_output, execution = build_verified_execution([EMPTY_REVIEW_FINDINGS])
    regression_service = services[6]

    regressions = regression_service.analyze(execution.execution_id)

    assert regressions == []
    assert regression_service.critical(execution.execution_id) is False


def test_behavioral_regression_is_critical():
    services, generated_output, execution = build_verified_execution([new_compatibility_finding_response()])
    regression_service = services[6]

    regressions = regression_service.analyze(execution.execution_id)

    assert len(regressions) == 1
    regression = regressions[0]
    assert regression.test_id == "COMPATIBILITY"
    assert regression.expected == {"blocking": False, "count": 0}
    assert regression.actual == {"blocking": True, "count": 1}
    assert regression.severity == "CRITICAL"
    assert regression_service.critical(execution.execution_id) is True


def test_critical_filtering_excludes_minor_only_regressions():
    services, generated_output, execution = build_verified_execution([new_quality_finding_response()])
    regression_service = services[6]

    regressions = regression_service.analyze(execution.execution_id)

    assert len(regressions) == 1
    assert regressions[0].severity == "MINOR"
    assert regression_service.critical(execution.execution_id) is False


def test_missing_baseline():
    services, generated_output, execution = build_verified_execution([EMPTY_REVIEW_FINDINGS])
    review_service = services[0]
    fix_service = services[1]
    patch_service = services[2]
    regression_service = services[6]

    plan = patch_service.get(execution.plan_id)
    suggestion = fix_service.get(plan.suggestion_id)
    del review_service._reviews[suggestion.review_id]

    with pytest.raises(MissingBaselineError):
        regression_service.analyze(execution.execution_id)


def test_invalid_execution_never_verified():
    services, generated_output, execution = build_verified_execution([EMPTY_REVIEW_FINDINGS])
    regression_service = services[6]

    with pytest.raises(UnknownPatchVerificationError):
        regression_service.analyze("no-such-execution")


def test_invalid_execution_failed_syntax():
    services, generated_output, execution = build_verified_execution([EMPTY_REVIEW_FINDINGS])
    verification_service = services[5]
    regression_service = services[6]
    # Simulate the generated output being corrupted after verification --
    # a fresh verify() call now reports syntax_valid False.
    generated_output.output["source"] = "def broken(:\n    pass"
    verification_service.verify(execution.execution_id)

    with pytest.raises(UnverifiedPatchError):
        regression_service.analyze(execution.execution_id)


def test_regression_result_validation():
    services, generated_output, execution = build_verified_execution([new_compatibility_finding_response()])
    regression_service = services[6]

    with pytest.raises(UnknownRegressionAnalysisError):
        regression_service.regressions(execution.execution_id)
    with pytest.raises(UnknownRegressionAnalysisError):
        regression_service.critical(execution.execution_id)

    regressions = regression_service.analyze(execution.execution_id)

    assert len(regressions) == 1
    regression = regressions[0]
    assert regression.execution_id == execution.execution_id
    assert regression.test_id in CATEGORIES
    assert regression.severity in {"CRITICAL", "MINOR"}
    assert set(regression.expected) == {"blocking", "count"}
    assert set(regression.actual) == {"blocking", "count"}
    assert regression_service.regressions(execution.execution_id) == regressions
