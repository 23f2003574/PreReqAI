import dataclasses
import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_validation import (
    LLMCodePatchValidationService,
    MalformedPatchValidationResponseError,
    UnknownPatchValidationError,
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
    return review_service, fix_service, patch_service, validation_service, provider


EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": [], "confidence": 1.0})

ONE_SUGGESTION_RESPONSE = json.dumps(
    {
        "suggestions": [
            {
                "finding_index": 0,
                "change": "Re-run the compiler after fixing the underlying plan issue.",
                "rationale": "The job failed, so there is no successfully generated code yet.",
                "confidence": 0.8,
                "risk": "LOW",
            }
        ]
    }
)

ONE_OPERATION_RESPONSE = json.dumps(
    {
        "operations": [{"op": "REPLACE", "location": "job-1", "value": "resolved"}],
        "rationale": "Mark the job as resolved once the plan issue is fixed and recompiled.",
    }
)

EMPTY_VALIDATION_FINDINGS = json.dumps({"findings": []})


def build_ready_plan(extra_scripts, job_id="job-1"):
    """A FAILED compiler job always produces exactly one deterministic
    CRITICAL CORRECTNESS finding without an LLM call, so it's a minimal,
    single-finding review/suggestion/plan chain to validate against."""
    review_service, fix_service, patch_service, validation_service, provider = build_services(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(ONE_OPERATION_RESPONSE), *extra_scripts]
    )
    generated_output = CompilerJobResult(job_id=job_id, status="FAILED", output={})
    review = review_service.review(generated_output)
    suggestion = fix_service.suggest(review.review_id)[0]
    plan = patch_service.plan(suggestion.suggestion_id)
    return review_service, fix_service, patch_service, validation_service, provider, review, suggestion, plan


def test_valid_patch():
    review_service, fix_service, patch_service, validation_service, provider, review, suggestion, plan = (
        build_ready_plan([make_response(EMPTY_VALIDATION_FINDINGS)])
    )

    validation = validation_service.validate(plan.plan_id)

    assert validation.plan_id == plan.plan_id
    assert validation.valid is True
    assert validation.findings == []
    assert validation_service.blocking(plan.plan_id) is False
    assert validation_service.findings(plan.plan_id) == []


def test_stale_target():
    review_service, fix_service, patch_service, validation_service, provider, review, suggestion, plan = (
        build_ready_plan([make_response(EMPTY_VALIDATION_FINDINGS)])
    )
    # Simulate the suggestion's grounding drifting away from the real
    # finding it was built from -- reuses Commit #2's own validate() logic,
    # which is exactly the check LLMCodePatchValidationService relies on.
    drifted = dataclasses.replace(suggestion, target="moved-elsewhere")
    fix_service._suggestions[suggestion.suggestion_id] = drifted

    validation = validation_service.validate(plan.plan_id)

    assert validation.valid is False
    assert any(finding["category"] == "STALE_TARGET" for finding in validation.findings)


def test_conflicting_operations():
    ambiguous_response = json.dumps(
        {
            "operations": [
                {"op": "REPLACE", "location": "job-1", "value": "resolved"},
                {"op": "REMOVE", "location": "job-1"},
            ],
            "rationale": "Conflicting proposals for the same location.",
        }
    )
    review_service, fix_service, patch_service, validation_service, provider = build_services(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(ambiguous_response), make_response(EMPTY_VALIDATION_FINDINGS)]
    )
    generated_output = CompilerJobResult(job_id="job-1", status="FAILED", output={})
    review = review_service.review(generated_output)
    suggestion = fix_service.suggest(review.review_id)[0]
    plan = patch_service.plan(suggestion.suggestion_id)
    assert plan.status == "REJECTED"

    validation = validation_service.validate(plan.plan_id)

    assert validation.valid is False
    assert any(finding["category"] == "CONFLICTING_OPERATIONS" for finding in validation.findings)


def test_syntax_failure_and_compiler_validation_integration():
    """End to end: a real CompilerJobResult with an embedded secret drives a
    real Commit #1 review, a real Commit #2 suggestion, and a real Commit
    #3 patch plan whose proposed replacement source is syntactically
    broken -- proving the deterministic `ast` check integrates with the
    actual generated-code pipeline, not a synthetic plan object."""
    bad_syntax_operation_response = json.dumps(
        {
            "operations": [{"op": "REPLACE", "location": "source", "value": "def add(a, b)\n    return a + b"}],
            "rationale": "Fix the hardcoded credential by removing it from the source.",
        }
    )
    review_service, fix_service, patch_service, validation_service, provider = build_services(
        [
            make_response(EMPTY_FINDINGS_RESPONSE),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(bad_syntax_operation_response),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    generated_output = CompilerJobResult(
        job_id="job-3",
        status="SUCCEEDED",
        output={"source": "def add(a, b):\n    api_key = 'sk-abcdefghijklmnop'\n    return a + b"},
    )
    review = review_service.review(generated_output)
    assert review.findings[0]["location"] == "source"

    suggestion = fix_service.suggest(review.review_id)[0]
    assert suggestion.target == "source"

    plan = patch_service.plan(suggestion.suggestion_id)
    assert plan.status == "READY"

    validation = validation_service.validate(plan.plan_id)

    assert validation.valid is False
    assert any(finding["category"] == "SYNTAX_ERROR" for finding in validation.findings)
    assert validation_service.blocking(plan.plan_id) is True


def test_blocking_finding_from_llm_response():
    llm_blocking_response = json.dumps(
        {
            "findings": [
                {
                    "category": "PROJECT_CONSTRAINT",
                    "target": "job-1",
                    "message": "value type is incompatible with the compiler's expected schema",
                    "blocking": True,
                }
            ]
        }
    )
    review_service, fix_service, patch_service, validation_service, provider, review, suggestion, plan = (
        build_ready_plan([make_response(llm_blocking_response)])
    )

    validation = validation_service.validate(plan.plan_id)

    assert validation.valid is False
    assert validation_service.blocking(plan.plan_id) is True


def test_malformed_llm_response_is_rejected():
    review_service, fix_service, patch_service, validation_service, provider, review, suggestion, plan = (
        build_ready_plan([make_response("not json")])
    )

    with pytest.raises(MalformedPatchValidationResponseError):
        validation_service.validate(plan.plan_id)


def test_unknown_validation_raises():
    review_service, fix_service, patch_service, validation_service, provider = build_services(
        [make_response(EMPTY_VALIDATION_FINDINGS)]
    )

    with pytest.raises(UnknownPatchValidationError):
        validation_service.findings("no-such-plan")
    with pytest.raises(UnknownPatchValidationError):
        validation_service.blocking("no-such-plan")


def test_source_immutability():
    review_service, fix_service, patch_service, validation_service, provider, review, suggestion, plan = (
        build_ready_plan([make_response(EMPTY_VALIDATION_FINDINGS)])
    )
    original_operations = list(plan.operations)

    validation_service.validate(plan.plan_id)

    assert patch_service.get(plan.plan_id).operations == original_operations
