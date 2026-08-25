import json

import pytest

from backend.api_candidates import LLMAPICandidateService
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
from backend.transformation_regression import (
    CRITICAL,
    MINOR,
    LLMTransformationRegressionService,
    MissingBaselineError,
    UnknownRegressionAnalysisError,
    UnknownRegressionError,
)
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

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "test_generation": test_generation_service,
        "transformation": transformation_service,
        "validation": validation_service,
        "diff": diff_service,
        "approval": approval_service,
        "execution": execution_service,
        "verification": verification_service,
        "regression": regression_service,
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

NO_REGRESSION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Add type hints only.",
                "proposed_source": "def add(a: int, b: int) -> dict:\n    return {'sum': a + b}",
            }
        ],
        "rationale": "Type hints improve readability; behavior is unchanged.",
        "confidence": 0.9,
    }
)
OUTPUT_REGRESSION_RESPONSE = json.dumps(
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
BEHAVIOR_MISMATCH_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Give b a default value.",
                "proposed_source": "def add(a: int, b: int = 0) -> dict:\n    return {'sum': a + b}",
            }
        ],
        "rationale": "b is now optional.",
        "confidence": 0.6,
    }
)
MIXED_REGRESSION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Off-by-one bug and a default value for b.",
                "proposed_source": "def add(a: int, b: int = 0) -> dict:\n    return {'sum': a + b + 1}",
            }
        ],
        "rationale": "Intentionally introduces both kinds of behavior change.",
        "confidence": 0.4,
    }
)

REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "refactor add"}


def _happy_env(transformation_response):
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(transformation_response),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    env["test_generation"].generate(candidate.candidate_id)
    return env


def _verified_execution(env, notebook_id="nb-1"):
    plan = env["transformation"].plan(notebook_id, REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    execution = env["execution"].apply(diff.diff_id)
    env["verification"].verify(execution.execution_id)
    return execution


def test_no_regression_when_behavior_is_unchanged():
    env = _happy_env(NO_REGRESSION_RESPONSE)
    execution = _verified_execution(env)

    regressions = env["regression"].analyze(execution.execution_id)

    assert regressions == []
    assert env["regression"].regressions(execution.execution_id) == []
    assert env["regression"].critical(execution.execution_id) is False


def test_output_regression_is_detected_with_expected_and_actual_values():
    env = _happy_env(OUTPUT_REGRESSION_RESPONSE)
    execution = _verified_execution(env)

    regressions = env["regression"].analyze(execution.execution_id)

    valid_regression = next(r for r in regressions if r.expected["value"] == {"sum": 3})
    assert valid_regression.severity == CRITICAL
    assert valid_regression.actual["value"] == {"sum": 4}
    assert valid_regression.expected["raised"] is False
    assert valid_regression.actual["raised"] is False


def test_behavior_mismatch_on_invalid_input_is_a_minor_regression():
    env = _happy_env(BEHAVIOR_MISMATCH_RESPONSE)
    execution = _verified_execution(env)

    regressions = env["regression"].analyze(execution.execution_id)

    assert len(regressions) == 1
    regression = regressions[0]
    assert regression.severity == MINOR
    assert regression.expected["raised"] is True
    assert regression.actual["raised"] is False


def test_critical_filtering_distinguishes_severities():
    minor_env = _happy_env(BEHAVIOR_MISMATCH_RESPONSE)
    minor_execution = _verified_execution(minor_env)
    minor_env["regression"].analyze(minor_execution.execution_id)
    assert minor_env["regression"].critical(minor_execution.execution_id) is False

    mixed_env = _happy_env(MIXED_REGRESSION_RESPONSE)
    mixed_execution = _verified_execution(mixed_env)
    regressions = mixed_env["regression"].analyze(mixed_execution.execution_id)

    severities = {r.severity for r in regressions}
    assert severities == {CRITICAL, MINOR}
    assert mixed_env["regression"].critical(mixed_execution.execution_id) is True


def test_missing_baseline_raises_when_no_generated_tests_exist():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(NO_REGRESSION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    # Deliberately never registered via api_candidate/input_schema/output_schema/test_generation.
    execution = _verified_execution(env)

    with pytest.raises(MissingBaselineError):
        env["regression"].analyze(execution.execution_id)

    with pytest.raises(UnknownRegressionAnalysisError):
        env["regression"].regressions(execution.execution_id)


def test_regression_can_be_resolved_and_no_longer_blocks_release():
    env = _happy_env(MIXED_REGRESSION_RESPONSE)
    execution = _verified_execution(env)
    regressions = env["regression"].analyze(execution.execution_id)
    critical_regression = next(r for r in regressions if r.severity == CRITICAL)

    resolved = env["regression"].resolve(critical_regression.regression_id)

    assert resolved is True
    remaining = env["regression"].regressions(execution.execution_id)
    assert critical_regression.regression_id not in {r.regression_id for r in remaining}

    with pytest.raises(UnknownRegressionError):
        env["regression"].resolve("nonexistent-regression")
