import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_compatibility_review import LLMCodePatchCompatibilityService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_gate import LLMCodePatchGateService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_quality_review import LLMCodePatchQualityService
from backend.code_patch_regression import LLMCodePatchRegressionService
from backend.code_patch_release import (
    GatesNotEvaluatedError,
    GatesNotPassedError,
    LLMCodePatchReleaseService,
    UnknownReleaseCandidateError,
)
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
    gate_service = LLMCodePatchGateService(
        verification_service, regression_service, security_service, compatibility_service, quality_service
    )
    release_service = LLMCodePatchReleaseService(gate_service, execution_service, patch_service, fix_service, review_service)
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


def operation_response(value: str) -> str:
    return json.dumps(
        {
            "operations": [{"op": "REPLACE", "location": "source", "value": value}],
            "rationale": "Replace the source per the fix suggestion.",
        }
    )


def run_pipeline_through_gates(services, output, operation_value, job_id):
    """Runs Commit #1-#11 (review through gate evaluation) using whatever
    scripted responses are already queued on `services["provider"]`."""
    generated_output = CompilerJobResult(job_id=job_id, status="SUCCEEDED", output=output)
    review = services["review"].review(generated_output)
    suggestion = services["fix"].suggest(review.review_id)[0]
    plan = services["patch"].plan(suggestion.suggestion_id)
    services["validation"].validate(plan.plan_id)
    execution = services["execution"].apply(plan.plan_id)
    services["verification"].verify(execution.execution_id)
    services["regression"].analyze(execution.execution_id)
    services["security"].analyze(execution.execution_id)
    services["compatibility"].review(execution.execution_id)
    services["quality"].analyze(execution.execution_id)
    services["gate"].evaluate(execution.execution_id)
    return generated_output, execution


def build_passing_pipeline(job_id="job-1"):
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
    generated_output, execution = run_pipeline_through_gates(services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE, job_id)
    assert services["gate"].passed(execution.execution_id) is True
    return services, generated_output, execution


def test_successful_preparation():
    services, generated_output, execution = build_passing_pipeline()
    release_service = services["release"]

    candidate = release_service.prepare(execution.execution_id)

    assert candidate.execution_id == execution.execution_id
    assert candidate.status == "PREPARED"
    assert release_service.status(candidate.candidate_id) == "PREPARED"


def test_gate_enforcement_never_evaluated():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(CLEAN_SOURCE)),
            make_response(EMPTY_VALIDATION_FINDINGS),
        ]
    )
    generated_output = CompilerJobResult(job_id="job-1", status="SUCCEEDED", output={"source": LEAKY_SOURCE})
    review = services["review"].review(generated_output)
    suggestion = services["fix"].suggest(review.review_id)[0]
    plan = services["patch"].plan(suggestion.suggestion_id)
    services["validation"].validate(plan.plan_id)
    execution = services["execution"].apply(plan.plan_id)
    # Gates were never evaluated for this execution.

    with pytest.raises(GatesNotEvaluatedError):
        services["release"].prepare(execution.execution_id)


def test_gate_enforcement_not_passed():
    services = build_services(
        [
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(ONE_SUGGESTION_RESPONSE),
            make_response(operation_response(LEAKY_SOURCE)),  # ineffective fix
            make_response(EMPTY_VALIDATION_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_REVIEW_FINDINGS),
            make_response(EMPTY_SECURITY_FINDINGS),
            make_response(EMPTY_COMPATIBILITY_FINDINGS),
            make_response(EMPTY_QUALITY_FINDINGS),
        ]
    )
    generated_output, execution = run_pipeline_through_gates(services, {"source": LEAKY_SOURCE}, LEAKY_SOURCE, "job-1")
    assert services["gate"].passed(execution.execution_id) is False

    with pytest.raises(GatesNotPassedError):
        services["release"].prepare(execution.execution_id)


def test_failed_preparation_creates_no_candidate():
    services, generated_output, execution = build_passing_pipeline()
    # Force the gate check to fail by re-evaluating against a corrupted output.
    generated_output.output["source"] = "def broken(:\n    pass"
    services["provider"]._script.append(make_response(EMPTY_REVIEW_FINDINGS))
    services["verification"].verify(execution.execution_id)
    services["gate"].evaluate(execution.execution_id)
    assert services["gate"].passed(execution.execution_id) is False

    with pytest.raises(GatesNotPassedError):
        services["release"].prepare(execution.execution_id)

    with pytest.raises(UnknownReleaseCandidateError):
        services["release"].status(f"release-candidate-{execution.execution_id}-1")


def test_artifact_linkage():
    services, generated_output, execution = build_passing_pipeline()
    release_service = services["release"]

    candidate = release_service.prepare(execution.execution_id)

    assert candidate.artifacts["job_id"] == "job-1"
    assert candidate.artifacts["output"] == generated_output.output
    assert candidate.artifacts["output"] is not generated_output.output


def test_immutable_version():
    services, generated_output, execution = build_passing_pipeline(job_id="job-1")
    release_service = services["release"]
    first_candidate = release_service.prepare(execution.execution_id)

    # Apply a second, independent patch to the same job to earn a second candidate.
    provider = services["provider"]
    provider._script.extend(
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
    second_output, second_execution = run_pipeline_through_gates(
        services, {"source": LEAKY_SOURCE}, CLEAN_SOURCE, "job-1"
    )
    second_candidate = release_service.prepare(second_execution.execution_id)

    assert first_candidate.version != second_candidate.version
    assert first_candidate.version == "job-1-v1"
    assert second_candidate.version == "job-1-v2"

    # Invalidating the first candidate must never change its own version.
    # Both executions share job_id "job-1", so the live generated output
    # backend.generated_code_review now tracks for that job is the second
    # patch's own output -- corrupting it is what verify() will see.
    original_version = first_candidate.version
    second_output.output["source"] = "def broken(:\n    pass"
    provider._script.append(make_response(EMPTY_REVIEW_FINDINGS))
    services["verification"].verify(execution.execution_id)
    services["gate"].evaluate(execution.execution_id)
    assert release_service.validate(first_candidate.candidate_id) is False
    assert release_service.status(first_candidate.candidate_id) == "INVALIDATED"
    stored_version = services["release"]._candidates[first_candidate.candidate_id].version
    assert stored_version == original_version


def test_status_lifecycle():
    services, generated_output, execution = build_passing_pipeline()
    release_service = services["release"]
    candidate = release_service.prepare(execution.execution_id)

    assert release_service.status(candidate.candidate_id) == "PREPARED"
    assert release_service.validate(candidate.candidate_id) is True
    assert release_service.status(candidate.candidate_id) == "PREPARED"

    generated_output.output["source"] = "def broken(:\n    pass"
    services["provider"]._script.append(make_response(EMPTY_REVIEW_FINDINGS))
    services["verification"].verify(execution.execution_id)
    services["gate"].evaluate(execution.execution_id)

    assert release_service.validate(candidate.candidate_id) is False
    assert release_service.status(candidate.candidate_id) == "INVALIDATED"
