import json

import pytest

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_compatibility_review import LLMCodePatchCompatibilityService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_gate import LLMCodePatchGateService, UnknownGateEvaluationError
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_quality_review import LLMCodePatchQualityService
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
    gate_service = LLMCodePatchGateService(
        verification_service, regression_service, security_service, compatibility_service, quality_service
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
DEPENDENCY_SOURCE = "def add(a, b):\n    os.system('rm -rf /')\n    return a + b"

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


def run_full_pipeline(
    output,
    operation_value,
    verify_review_response=EMPTY_REVIEW_FINDINGS,
    regression_review_response=EMPTY_REVIEW_FINDINGS,
    security_response=EMPTY_SECURITY_FINDINGS,
    compatibility_response=EMPTY_COMPATIBILITY_FINDINGS,
    quality_response=EMPTY_QUALITY_FINDINGS,
    job_id="job-1",
):
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
            make_response(quality_response),
        ]
    )

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

    return services, generated_output, execution


def gates_by_type(gates):
    return {gate.gate_type: gate for gate in gates}


def test_all_gates_pass():
    services, generated_output, execution = run_full_pipeline({"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    gate_service = services["gate"]

    gates = gate_service.evaluate(execution.execution_id)

    assert len(gates) == 5
    assert {gate.gate_type for gate in gates} == {"VERIFICATION", "REGRESSION", "SECURITY", "COMPATIBILITY", "QUALITY"}
    assert all(gate.status == "PASSED" for gate in gates)
    assert gate_service.passed(execution.execution_id) is True
    assert gate_service.blocking(execution.execution_id) is False


def test_verification_failure():
    # An ineffective fix leaves the original credential in place, so
    # Commit #6's re-review still reports a blocking finding.
    services, generated_output, execution = run_full_pipeline({"source": LEAKY_SOURCE}, LEAKY_SOURCE)
    gate_service = services["gate"]

    gates = gates_by_type(gate_service.evaluate(execution.execution_id))

    assert gates["VERIFICATION"].status == "FAILED"
    assert gate_service.passed(execution.execution_id) is False


def test_regression_failure():
    services, generated_output, execution = run_full_pipeline(
        {"source": LEAKY_SOURCE}, CLEAN_SOURCE, regression_review_response=NEW_COMPATIBILITY_FINDING_RESPONSE
    )
    gate_service = services["gate"]

    gates = gates_by_type(gate_service.evaluate(execution.execution_id))

    assert gates["REGRESSION"].status == "FAILED"
    assert any(finding["category"] == "REGRESSION" for finding in gates["REGRESSION"].findings)
    assert gate_service.passed(execution.execution_id) is False


def test_security_failure():
    services, generated_output, execution = run_full_pipeline({"source": LEAKY_SOURCE}, DEPENDENCY_SOURCE)
    gate_service = services["gate"]

    gates = gates_by_type(gate_service.evaluate(execution.execution_id))

    assert gates["SECURITY"].status == "FAILED"
    assert gate_service.passed(execution.execution_id) is False


def test_compatibility_failure():
    output = {"source": LEAKY_SOURCE, "endpoints": [{"path": "add", "method": "FETCH"}]}
    services, generated_output, execution = run_full_pipeline(output, CLEAN_SOURCE)
    gate_service = services["gate"]

    gates = gates_by_type(gate_service.evaluate(execution.execution_id))

    assert gates["COMPATIBILITY"].status == "FAILED"
    assert gate_service.passed(execution.execution_id) is False


def test_quality_failure():
    services, generated_output, execution = run_full_pipeline(
        {"source": LEAKY_SOURCE}, CLEAN_SOURCE, regression_review_response=NEW_COMPATIBILITY_FINDING_RESPONSE
    )
    gate_service = services["gate"]

    gates = gates_by_type(gate_service.evaluate(execution.execution_id))

    assert gates["QUALITY"].status == "FAILED"
    assert gate_service.passed(execution.execution_id) is False


def test_missing_gate_fails_closed_for_unrun_prerequisites():
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
    # Deliberately never call verify(), regression.analyze(), or
    # compatibility.review() before evaluating gates.

    gates = gates_by_type(services["gate"].evaluate(execution.execution_id))

    assert gates["VERIFICATION"].status == "FAILED"
    assert any(f["category"] == "MISSING_VERIFICATION" for f in gates["VERIFICATION"].findings)
    assert gates["REGRESSION"].status == "FAILED"
    assert any(f["category"] == "MISSING_REGRESSION_ANALYSIS" for f in gates["REGRESSION"].findings)
    assert gates["COMPATIBILITY"].status == "FAILED"
    assert any(f["category"] == "MISSING_COMPATIBILITY_REVIEW" for f in gates["COMPATIBILITY"].findings)
    # SECURITY/QUALITY mirror their own services' read methods, which report
    # no findings (not an error) when nothing has been analyzed yet.
    assert gates["SECURITY"].status == "PASSED"
    assert gates["QUALITY"].status == "PASSED"
    assert services["gate"].passed(execution.execution_id) is False


def test_missing_gate_before_evaluate_raises():
    services, generated_output, execution = run_full_pipeline({"source": LEAKY_SOURCE}, CLEAN_SOURCE)
    gate_service = services["gate"]

    with pytest.raises(UnknownGateEvaluationError):
        gate_service.gates(execution.execution_id)
    with pytest.raises(UnknownGateEvaluationError):
        gate_service.blocking(execution.execution_id)
    with pytest.raises(UnknownGateEvaluationError):
        gate_service.passed(execution.execution_id)
