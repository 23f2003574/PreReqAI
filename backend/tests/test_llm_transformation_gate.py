import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.code_quality import LLMCodeQualityService
from backend.code_transformation import REFACTOR, LLMCodeTransformationService
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.output_schema import LLMOutputSchemaService
from backend.test_generation import LLMTestGenerationService
from backend.transformation_approval import LLMTransformationApprovalService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_gate import (
    FAILED,
    PASSED,
    QUALITY,
    REGRESSION,
    SECURITY,
    VERIFICATION,
    LLMTransformationGateService,
)
from backend.transformation_regression import LLMTransformationRegressionService
from backend.transformation_validation import LLMTransformationValidationService
from backend.transformation_verification import LLMTransformationVerificationService


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


def build_env(script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": ScriptedProvider(script)},
    )

    notebook_analysis_service = LLMNotebookAnalysisService(orchestration_service, context_service)
    api_candidate_service = LLMAPICandidateService(
        notebook_analysis_service, orchestration_service=orchestration_service, context_service=context_service
    )
    input_schema_service = LLMInputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    output_schema_service = LLMOutputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    test_generation_service = LLMTestGenerationService(
        api_candidate_service, input_schema_service, output_schema_service, orchestration_service, context_service
    )
    code_quality_service = LLMCodeQualityService(notebook_analysis_service, orchestration_service, context_service)

    transformation_service = LLMCodeTransformationService(
        notebook_analysis_service, orchestration_service, context_service
    )
    validation_service = LLMTransformationValidationService(
        transformation_service, notebook_analysis_service, orchestration_service, context_service
    )
    diff_service = LLMTransformationDiffService(
        transformation_service, validation_service, notebook_analysis_service
    )
    approval_service = LLMTransformationApprovalService(diff_service, validation_service)
    execution_service = LLMTransformationExecutionService(
        approval_service, diff_service, transformation_service, notebook_analysis_service
    )
    verification_service = LLMTransformationVerificationService(
        execution_service, diff_service, transformation_service, api_candidate_service, test_generation_service
    )
    regression_service = LLMTransformationRegressionService(
        verification_service,
        execution_service,
        diff_service,
        transformation_service,
        api_candidate_service,
        test_generation_service,
    )
    gate_service = LLMTransformationGateService(
        execution_service,
        diff_service,
        transformation_service,
        verification_service,
        regression_service,
        code_quality_service,
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "test_generation": test_generation_service,
        "code_quality": code_quality_service,
        "transformation": transformation_service,
        "validation": validation_service,
        "diff": diff_service,
        "approval": approval_service,
        "execution": execution_service,
        "verification": verification_service,
        "regression": regression_service,
        "gate": gate_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return {'sum': a + b}"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "add", "cell_index": 1}], "dependencies": []}
)
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "add",
                "inputs": ["a", "b"],
                "outputs": ["sum"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            }
        ]
    }
)
INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            {"name": "a", "type": "int", "constraints": {}, "ambiguous": False},
            {"name": "b", "type": "int", "constraints": {}, "ambiguous": False},
        ]
    }
)
OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "sum", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
TEST_GENERATION_RESPONSE = json.dumps(
    {
        "tests": [
            {
                "scenario": "adds two positive numbers",
                "category": "VALID",
                "input": {"a": 1, "b": 2},
                "expected_output": {"sum": 3},
                "confidence": 0.9,
            },
            {
                "scenario": "missing required field b",
                "category": "INVALID",
                "input": {"a": 1},
                "expected_output": {"raises": True, "reason": "b is required"},
                "confidence": 0.8,
            },
            {
                "scenario": "zeros",
                "category": "EDGE",
                "input": {"a": 0, "b": 0},
                "expected_output": {"sum": 0},
                "confidence": 0.7,
            },
        ]
    }
)
EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})

COMPATIBLE_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Add type hints.",
                "proposed_source": "def add(a: int, b: int) -> dict:\n    return {'sum': a + b}",
            }
        ],
        "rationale": "Type hints improve readability.",
        "confidence": 0.9,
    }
)
BREAKING_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Off-by-one bug.",
                "proposed_source": "def add(a: int, b: int) -> dict:\n    return {'sum': a + b + 1}",
            }
        ],
        "rationale": "Intentionally introduces a bug for the test.",
        "confidence": 0.5,
    }
)
DANGEROUS_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Log via exec for debugging.",
                "proposed_source": "def add(a: int, b: int) -> dict:\n    exec('pass')\n    return {'sum': a + b}",
            }
        ],
        "rationale": "Adds a debug hook.",
        "confidence": 0.4,
    }
)
QUALITY_ERROR_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "cell_id": "cell:1",
                "category": "RISK",
                "severity": "ERROR",
                "message": "exec() usage is a serious risk.",
                "confidence": 0.9,
            }
        ]
    }
)

REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "refactor add"}


def _register_candidate_and_tests(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    env["test_generation"].generate(candidate.candidate_id)
    return analysis, candidate


def _applied_execution(env):
    plan = env["transformation"].plan("nb-1", REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    return env["execution"].apply(diff.diff_id)


def test_all_gates_pass_for_a_clean_transformation():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(COMPATIBLE_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    _register_candidate_and_tests(env)
    execution = _applied_execution(env)
    env["verification"].verify(execution.execution_id)
    env["regression"].analyze(execution.execution_id)

    gates = env["gate"].evaluate(execution.execution_id)

    assert {g.gate_type for g in gates} == {VERIFICATION, REGRESSION, SECURITY, QUALITY}
    assert all(g.status == PASSED for g in gates)
    assert env["gate"].passed(execution.execution_id) is True
    assert env["gate"].blocking(execution.execution_id) is False


def test_verification_failure_blocks_the_verification_gate():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(COMPATIBLE_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    execution = _applied_execution(env)
    # Deliberately never verified.

    gates = env["gate"].evaluate(execution.execution_id)

    verification_gate = next(g for g in gates if g.gate_type == VERIFICATION)
    assert verification_gate.status == FAILED
    assert env["gate"].blocking(execution.execution_id) is True


def test_regression_failure_blocks_the_regression_gate():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(BREAKING_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    _register_candidate_and_tests(env)
    execution = _applied_execution(env)
    env["verification"].verify(execution.execution_id)
    env["regression"].analyze(execution.execution_id)

    gates = env["gate"].evaluate(execution.execution_id)

    regression_gate = next(g for g in gates if g.gate_type == REGRESSION)
    assert regression_gate.status == FAILED
    assert any(f["blocking"] for f in regression_gate.findings)


def test_security_and_quality_findings_block_their_gates():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(DANGEROUS_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
            make_response(QUALITY_ERROR_RESPONSE),
        ]
    )
    analysis, _candidate = _register_candidate_and_tests(env)
    execution = _applied_execution(env)
    env["verification"].verify(execution.execution_id)
    env["regression"].analyze(execution.execution_id)
    env["code_quality"].analyze(analysis.analysis_id)

    gates = env["gate"].evaluate(execution.execution_id)

    security_gate = next(g for g in gates if g.gate_type == SECURITY)
    quality_gate = next(g for g in gates if g.gate_type == QUALITY)
    assert security_gate.status == FAILED
    assert quality_gate.status == FAILED
    assert env["gate"].passed(execution.execution_id) is False


def test_missing_regression_analysis_fails_the_gate_closed():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(COMPATIBLE_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    _register_candidate_and_tests(env)
    execution = _applied_execution(env)
    env["verification"].verify(execution.execution_id)
    # Deliberately never ran regression analysis.

    gates = env["gate"].evaluate(execution.execution_id)

    verification_gate = next(g for g in gates if g.gate_type == VERIFICATION)
    regression_gate = next(g for g in gates if g.gate_type == REGRESSION)
    assert verification_gate.status == PASSED
    assert regression_gate.status == FAILED
    assert regression_gate.findings[0]["category"] == "MISSING_REGRESSION_ANALYSIS"


def test_evaluation_is_deterministic_across_repeated_calls():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(COMPATIBLE_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    _register_candidate_and_tests(env)
    execution = _applied_execution(env)
    env["verification"].verify(execution.execution_id)
    env["regression"].analyze(execution.execution_id)

    first = env["gate"].evaluate(execution.execution_id)
    second = env["gate"].evaluate(execution.execution_id)

    first_summary = [(g.gate_type, g.status, g.findings) for g in first]
    second_summary = [(g.gate_type, g.status, g.findings) for g in second]
    assert first_summary == second_summary
