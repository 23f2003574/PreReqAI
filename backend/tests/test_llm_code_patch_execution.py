import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import (
    AlreadyAppliedError,
    ApplicationNotValidatedError,
    InvalidRollbackStateError,
    LLMCodePatchExecutionService,
    PatchNotValidError,
    UnknownExecutionError,
)
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_validation import LLMCodePatchValidationService, UnknownPatchValidationError
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
    return review_service, fix_service, patch_service, validation_service, execution_service, provider


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


def build_applyable_execution(job_id="job-1"):
    """A real, end-to-end pipeline: a SUCCEEDED compiler job whose source
    contains a hardcoded secret drives a real Commit #1 review, a real
    Commit #2 suggestion, a real Commit #3 plan, and a real Commit #4
    validation that comes back clean -- everything apply() needs."""
    review_service, fix_service, patch_service, validation_service, execution_service, provider = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(GOOD_OPERATION_RESPONSE),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    generated_output = CompilerJobResult(job_id=job_id, status="SUCCEEDED", output={"source": LEAKY_SOURCE})
    review = review_service.review(generated_output)
    suggestion = fix_service.suggest(review.review_id)[0]
    plan = patch_service.plan(suggestion.suggestion_id)
    assert plan.status == "READY"
    validation = validation_service.validate(plan.plan_id)
    assert validation.valid is True

    return review_service, fix_service, patch_service, validation_service, execution_service, generated_output, plan


def test_successful_application():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        generated_output,
        plan,
    ) = build_applyable_execution()

    execution = execution_service.apply(plan.plan_id)

    assert execution.plan_id == plan.plan_id
    assert execution.status == "SUCCEEDED"
    assert generated_output.output["source"] == CLEAN_SOURCE
    assert execution_service.status(execution.execution_id) == "SUCCEEDED"


def test_changed_file_tracking():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        generated_output,
        plan,
    ) = build_applyable_execution()

    execution = execution_service.apply(plan.plan_id)

    assert execution.changed_files == ("source",)


def test_validation_requirement_never_validated():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        generated_output,
        plan,
    ) = build_applyable_execution()

    with pytest.raises(UnknownPatchValidationError):
        execution_service.apply("never-validated-plan-id")


def test_validation_requirement_blocking():
    review_service, fix_service, patch_service, validation_service, execution_service, provider = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(GOOD_OPERATION_RESPONSE),
            make_response(
                json.dumps(
                    {
                        "findings": [
                            {
                                "category": "PROJECT_CONSTRAINT",
                                "target": "source",
                                "message": "still not safe to apply",
                                "blocking": True,
                            }
                        ]
                    }
                )
            ),
        ]
    )
    generated_output = CompilerJobResult(job_id="job-2", status="SUCCEEDED", output={"source": LEAKY_SOURCE})
    review = review_service.review(generated_output)
    suggestion = fix_service.suggest(review.review_id)[0]
    plan = patch_service.plan(suggestion.suggestion_id)
    validation = validation_service.validate(plan.plan_id)
    assert validation.valid is False

    with pytest.raises(PatchNotValidError):
        execution_service.apply(plan.plan_id)

    assert generated_output.output["source"] == LEAKY_SOURCE


def test_atomic_failure_leaves_output_unchanged():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        generated_output,
        plan,
    ) = build_applyable_execution()
    # Simulate the generated output drifting out from under the plan
    # between validation and application.
    del generated_output.output["source"]

    with pytest.raises(ApplicationNotValidatedError):
        execution_service.apply(plan.plan_id)

    assert "source" not in generated_output.output
    assert plan.plan_id not in execution_service._execution_id_by_plan


def test_rollback():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        generated_output,
        plan,
    ) = build_applyable_execution()
    execution = execution_service.apply(plan.plan_id)
    assert generated_output.output["source"] == CLEAN_SOURCE

    rolled_back = execution_service.rollback(execution.execution_id)

    assert rolled_back.status == "ROLLED_BACK"
    assert generated_output.output["source"] == LEAKY_SOURCE
    assert execution_service.status(execution.execution_id) == "ROLLED_BACK"


def test_rollback_requires_succeeded_status():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        generated_output,
        plan,
    ) = build_applyable_execution()
    execution = execution_service.apply(plan.plan_id)
    execution_service.rollback(execution.execution_id)

    with pytest.raises(InvalidRollbackStateError):
        execution_service.rollback(execution.execution_id)


def test_duplicate_application_rejection():
    (
        review_service,
        fix_service,
        patch_service,
        validation_service,
        execution_service,
        generated_output,
        plan,
    ) = build_applyable_execution()
    execution_service.apply(plan.plan_id)

    with pytest.raises(AlreadyAppliedError):
        execution_service.apply(plan.plan_id)


def test_unknown_execution_raises():
    review_service, fix_service, patch_service, validation_service, execution_service, provider = build_services(
        [make_response(EMPTY_REVIEW_FINDINGS)]
    )

    with pytest.raises(UnknownExecutionError):
        execution_service.status("no-such-execution")
    with pytest.raises(UnknownExecutionError):
        execution_service.rollback("no-such-execution")
