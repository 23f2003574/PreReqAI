import copy
import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService, UnknownSuggestionError
from backend.code_patch_planning import (
    LLMCodePatchService,
    MalformedPatchPlanResponseError,
    UnknownPatchPlanError,
    UnsupportedPatchTargetError,
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
    return review_service, fix_service, patch_service, provider


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


def build_validated_suggestion(script, job_id="job-1"):
    """A FAILED compiler job always produces exactly one deterministic
    CRITICAL CORRECTNESS finding without an LLM call, so its one finding's
    location (the job_id itself) is a minimal, stable target to plan a
    patch against."""
    review_service, fix_service, patch_service, provider = build_services(script)
    generated_output = CompilerJobResult(job_id=job_id, status="FAILED", output={})
    review = review_service.review(generated_output)
    return review_service, fix_service, patch_service, provider, review


ONE_OPERATION_RESPONSE = json.dumps(
    {
        "operations": [{"op": "REPLACE", "location": "job-1", "value": "resolved"}],
        "rationale": "Mark the job as resolved once the plan issue is fixed and recompiled.",
    }
)


def test_plan_generation():
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(ONE_OPERATION_RESPONSE)]
    )
    suggestion = fix_service.suggest(review.review_id)[0]

    plan = patch_service.plan(suggestion.suggestion_id)

    assert plan.suggestion_id == suggestion.suggestion_id
    assert plan.target == suggestion.target == "job-1"
    assert plan.status == "READY"
    assert plan.operations == [{"op": "REPLACE", "location": "job-1", "value": "resolved"}]
    assert plan.rationale == "Mark the job as resolved once the plan issue is fixed and recompiled."
    assert patch_service.validate(plan.plan_id) is True


def test_unknown_suggestion_propagates_commit2_error():
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE)]
    )

    with pytest.raises(UnknownSuggestionError):
        patch_service.plan("no-such-suggestion")


def test_target_validation_rejects_operation_on_a_different_location():
    wrong_target_response = json.dumps(
        {
            "operations": [{"op": "REPLACE", "location": "not-the-target", "value": "x"}],
            "rationale": "y",
        }
    )
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(wrong_target_response)]
    )
    suggestion = fix_service.suggest(review.review_id)[0]

    with pytest.raises(UnsupportedPatchTargetError):
        patch_service.plan(suggestion.suggestion_id)


@pytest.mark.parametrize(
    "malformed_response",
    [
        "not json",
        json.dumps({"operations": []}),
        json.dumps({"operations": "not-a-list"}),
        json.dumps({"operations": [{"op": "DELETE", "location": "job-1"}], "rationale": "y"}),
        json.dumps({"operations": [{"op": "REPLACE", "location": "job-1"}], "rationale": "y"}),
        json.dumps({"operations": [{"op": "REPLACE", "location": "job-1", "value": "x"}]}),
        json.dumps({"operations": [{"op": "REPLACE", "location": "job-1", "value": "x"}], "rationale": ""}),
    ],
)
def test_operation_validation_rejects_malformed_operations(malformed_response):
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(malformed_response)]
    )
    suggestion = fix_service.suggest(review.review_id)[0]

    with pytest.raises(MalformedPatchPlanResponseError):
        patch_service.plan(suggestion.suggestion_id)


def test_ambiguous_plan_rejection():
    ambiguous_response = json.dumps(
        {
            "operations": [
                {"op": "REPLACE", "location": "job-1", "value": "resolved"},
                {"op": "REMOVE", "location": "job-1"},
            ],
            "rationale": "Conflicting proposals for the same location.",
        }
    )
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(ambiguous_response)]
    )
    suggestion = fix_service.suggest(review.review_id)[0]

    plan = patch_service.plan(suggestion.suggestion_id)

    assert plan.status == "REJECTED"
    assert len(plan.operations) == 2
    assert patch_service.validate(plan.plan_id) is False


def test_preview():
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(ONE_OPERATION_RESPONSE)]
    )
    suggestion = fix_service.suggest(review.review_id)[0]
    plan = patch_service.plan(suggestion.suggestion_id)

    preview = patch_service.preview(plan.plan_id)

    assert preview == ["REPLACE job-1 -> 'resolved'"]


def test_preview_unknown_plan_raises():
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE)]
    )

    with pytest.raises(UnknownPatchPlanError):
        patch_service.preview("no-such-plan")
    with pytest.raises(UnknownPatchPlanError):
        patch_service.validate("no-such-plan")


def test_source_immutability():
    review_service, fix_service, patch_service, provider, review = build_validated_suggestion(
        [make_response(ONE_SUGGESTION_RESPONSE), make_response(ONE_OPERATION_RESPONSE)]
    )
    suggestion = fix_service.suggest(review.review_id)[0]
    original_findings = copy.deepcopy(review.findings)
    original_suggestion = copy.deepcopy(suggestion)

    patch_service.plan(suggestion.suggestion_id)

    assert review.findings == original_findings
    assert fix_service.get(suggestion.suggestion_id) == original_suggestion
