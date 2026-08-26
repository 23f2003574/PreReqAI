import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_compatibility_review import LLMCodePatchCompatibilityService
from backend.code_patch_execution import ApplicationNotValidatedError, LLMCodePatchExecutionService
from backend.code_patch_gate import LLMCodePatchGateService
from backend.code_patch_orchestration import (
    LLMCodePatchOrchestrationService,
    NotReadyForReleaseError,
    UnknownDecisionError,
)
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_quality_review import LLMCodePatchQualityService
from backend.code_patch_regression import LLMCodePatchRegressionService
from backend.code_patch_release import LLMCodePatchReleaseService
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
    orchestration_llm_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": provider},
    )

    review_service = LLMGeneratedCodeReviewService(orchestration_llm_service, context_service)
    fix_service = LLMCodeFixSuggestionService(review_service, orchestration_llm_service, context_service)
    patch_service = LLMCodePatchService(review_service, fix_service, orchestration_llm_service, context_service)
    validation_service = LLMCodePatchValidationService(
        fix_service, patch_service, orchestration_llm_service, context_service
    )
    execution_service = LLMCodePatchExecutionService(review_service, fix_service, patch_service, validation_service)
    verification_service = LLMCodePatchVerificationService(
        execution_service, review_service, fix_service, patch_service
    )
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
        orchestration_llm_service,
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
        orchestration_llm_service,
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
        orchestration_llm_service,
        context_service,
    )
    gate_service = LLMCodePatchGateService(
        verification_service, regression_service, security_service, compatibility_service, quality_service
    )
    release_service = LLMCodePatchReleaseService(
        gate_service, execution_service, patch_service, fix_service, review_service
    )
    orchestration_service = LLMCodePatchOrchestrationService(
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
        gate_service,
        release_service,
    )
    return {
        "review": review_service,
        "fix": fix_service,
        "patch": patch_service,
        "validation": validation_service,
        "execution": execution_service,
        "verification": verification_service,
        "regression": regression_service,
        "security": security_service,
        "compatibility": compatibility_service,
        "quality": quality_service,
        "gate": gate_service,
        "release": release_service,
        "orchestration": orchestration_service,
        "provider": provider,
    }


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

CLEAN_SOURCE = "def add(a, b):\n    return a + b"
LEAKY_SOURCE = "def add(a, b):\n    api_key = 'sk-abcdefghijklmnop'\n    return a + b"

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

CRITICAL_SECURITY_FINDING_RESPONSE = json.dumps(
    {
        "findings": [
            {"category": "SECRETS", "severity": "CRITICAL", "evidence": "LLM-detected residual secret risk", "confidence": 0.9}
        ]
    }
)

CRITICAL_QUALITY_FINDING_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "category": "MAINTAINABILITY",
                "severity": "CRITICAL",
                "location": "source",
                "evidence": "LLM-detected unmaintainable structure",
                "confidence": 0.9,
            }
        ]
    }
)


def operation_response(value: str) -> str:
    return json.dumps(
        {
            "operations": [{"op": "REPLACE", "location": "source", "value": value}],
            "rationale": "Replace the source per the fix suggestion.",
        }
    )


def run_review_and_plan(services, output, operation_value, job_id="job-1"):
    generated_output = CompilerJobResult(job_id=job_id, status="SUCCEEDED", output=output)
    review = services["orchestration"].review(generated_output)
    plan = services["orchestration"].prepare_patch(review.review_id)
    return generated_output, review, plan


def test_successful_end_to_end_patch_and_release_candidate():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_SECURITY_FINDINGS),
            make_response(EMPTY_COMPATIBILITY_FINDINGS),
            make_response(EMPTY_QUALITY_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)

    applied_decision = orchestration.apply(plan.plan_id)
    assert applied_decision.status == "APPLIED"
    execution_id = applied_decision.execution_id

    verified_decision = orchestration.verify(execution_id)
    assert verified_decision.status == "READY_FOR_RELEASE"
    assert verified_decision.blocking_findings == []

    released_decision = orchestration.release(execution_id)

    assert released_decision.status == "RELEASED"
    assert released_decision.release_candidate_id is not None
    assert services["release"].status(released_decision.release_candidate_id) == "PREPARED"
    assert generated_output.output["source"] == CLEAN_SOURCE
    assert orchestration.decision(execution_id) == released_decision


def test_validation_rejection():
    ambiguous_response = json.dumps(
        {
            "operations": [
                {"op": "REPLACE", "location": "job-1", "value": "resolved"},
                {"op": "REMOVE", "location": "job-1"},
            ],
            "rationale": "Conflicting proposals for the same location.",
        }
    )
    services = build_services(
        [
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(ambiguous_response),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output = CompilerJobResult(job_id="job-1", status="FAILED", output={})
    review = orchestration.review(generated_output)
    plan = orchestration.prepare_patch(review.review_id)
    assert plan.status == "REJECTED"

    decision = orchestration.apply(plan.plan_id)

    assert decision.status == "REJECTED"
    assert decision.execution_id is None
    assert "CONFLICTING_OPERATIONS" in decision.blocking_findings


def test_application_failure_propagates_and_creates_no_decision():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    # Simulate the generated output drifting out from under the plan
    # between planning and application -- Commit #4's validate() doesn't
    # read the live output, so this only surfaces inside Commit #5's own
    # atomic apply(), which must raise before writing anything.
    del generated_output.output["source"]

    with pytest.raises(ApplicationNotValidatedError):
        orchestration.apply(plan.plan_id)

    assert "source" not in generated_output.output


def test_verification_failure_rolls_back():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(LEAKY_SOURCE)),  # ineffective fix
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, LEAKY_SOURCE)
    execution_id = orchestration.apply(plan.plan_id).execution_id

    decision = orchestration.verify(execution_id)

    assert decision.status == "ROLLED_BACK"
    assert decision.blocking_findings == ["VERIFICATION"]
    assert services["execution"].status(execution_id) == "ROLLED_BACK"


def test_regression_failure_rolls_back():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(NEW_COMPATIBILITY_FINDING_RESPONSE),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    execution_id = orchestration.apply(plan.plan_id).execution_id

    decision = orchestration.verify(execution_id)

    assert decision.status == "ROLLED_BACK"
    assert decision.blocking_findings == ["REGRESSION"]


def test_security_failure_rolls_back():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(CRITICAL_SECURITY_FINDING_RESPONSE),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    execution_id = orchestration.apply(plan.plan_id).execution_id

    decision = orchestration.verify(execution_id)

    assert decision.status == "ROLLED_BACK"
    assert decision.blocking_findings == ["SECURITY"]


def test_compatibility_failure_rolls_back():
    output = {"source": LEAKY_SOURCE, "endpoints": [{"path": "add", "method": "FETCH"}]}
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_SECURITY_FINDINGS),
            make_response(EMPTY_COMPATIBILITY_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, output, CLEAN_SOURCE)
    execution_id = orchestration.apply(plan.plan_id).execution_id

    decision = orchestration.verify(execution_id)

    assert decision.status == "ROLLED_BACK"
    assert decision.blocking_findings == ["COMPATIBILITY"]


def test_quality_failure_rolls_back():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_SECURITY_FINDINGS),
            make_response(EMPTY_COMPATIBILITY_FINDINGS),
            make_response(CRITICAL_QUALITY_FINDING_RESPONSE),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    execution_id = orchestration.apply(plan.plan_id).execution_id

    decision = orchestration.verify(execution_id)

    assert decision.status == "ROLLED_BACK"
    assert decision.blocking_findings == ["QUALITY"]


def test_rollback_preserves_capability():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    execution_id = orchestration.apply(plan.plan_id).execution_id
    assert generated_output.output["source"] == CLEAN_SOURCE

    decision = orchestration.rollback(execution_id)

    assert decision.status == "ROLLED_BACK"
    assert decision.reason == "manually rolled back"
    assert services["execution"].status(execution_id) == "ROLLED_BACK"
    assert generated_output.output["source"] == LEAKY_SOURCE


def test_release_requires_ready_for_release_decision():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    execution_id = orchestration.apply(plan.plan_id).execution_id

    with pytest.raises(NotReadyForReleaseError):
        orchestration.release(execution_id)


def test_deterministic_decision():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_SECURITY_FINDINGS),
            make_response(EMPTY_COMPATIBILITY_FINDINGS),
            make_response(EMPTY_QUALITY_FINDINGS),
        ]
    )
    orchestration = services["orchestration"]
    generated_output, review, plan = run_review_and_plan(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE)

    applied = orchestration.apply(plan.plan_id)
    execution_id = applied.execution_id
    assert orchestration.decision(execution_id) == applied
    assert orchestration.decision(execution_id).status == "APPLIED"

    verified = orchestration.verify(execution_id)
    assert orchestration.decision(execution_id) == verified
    assert orchestration.decision(execution_id).status == "READY_FOR_RELEASE"
    assert verified.decision_id != applied.decision_id
    assert verified.execution_id == applied.execution_id

    released = orchestration.release(execution_id)
    assert orchestration.decision(execution_id) == released
    assert orchestration.decision(execution_id).status == "RELEASED"

    with pytest.raises(UnknownDecisionError):
        orchestration.decision("no-such-execution")
