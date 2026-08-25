import json
from dataclasses import FrozenInstanceError

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
from backend.transformation_gate import LLMTransformationGateService
from backend.transformation_regression import LLMTransformationRegressionService
from backend.transformation_release import (
    PREPARED,
    RELEASED,
    GatesNotEvaluatedError,
    GatesNotPassedError,
    LLMTransformationReleaseService,
    ReleaseNotPreparedError,
    UnknownReleaseError,
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
    release_service = LLMTransformationReleaseService(
        gate_service, execution_service, diff_service, transformation_service
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
        "release": release_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return {'sum': a + b}"},
        {"cell_type": "code", "source": "def sub(a, b):\n    return {'diff': a - b}"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "add", "cell_index": 1}, {"name": "sub", "cell_index": 2}],
        "dependencies": [],
    }
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
            },
            {
                "function_name": "sub",
                "inputs": ["a", "b"],
                "outputs": ["diff"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            },
        ]
    }
)
ADD_INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            {"name": "a", "type": "int", "constraints": {}, "ambiguous": False},
            {"name": "b", "type": "int", "constraints": {}, "ambiguous": False},
        ]
    }
)
SUB_INPUT_SCHEMA_RESPONSE = ADD_INPUT_SCHEMA_RESPONSE
ADD_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "sum", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
SUB_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "diff", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
ADD_TEST_GENERATION_RESPONSE = json.dumps(
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
SUB_TEST_GENERATION_RESPONSE = json.dumps(
    {
        "tests": [
            {
                "scenario": "subtracts two positive numbers",
                "category": "VALID",
                "input": {"a": 5, "b": 2},
                "expected_output": {"diff": 3},
                "confidence": 0.9,
            },
            {
                "scenario": "missing required field b",
                "category": "INVALID",
                "input": {"a": 5},
                "expected_output": {"raises": True, "reason": "b is required"},
                "confidence": 0.8,
            },
            {
                "scenario": "zeros",
                "category": "EDGE",
                "input": {"a": 0, "b": 0},
                "expected_output": {"diff": 0},
                "confidence": 0.7,
            },
        ]
    }
)
EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})

ADD_TRANSFORMATION_RESPONSE = json.dumps(
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
SUB_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 2,
                "description": "Add type hints.",
                "proposed_source": "def sub(a: int, b: int) -> dict:\n    return {'diff': a - b}",
            }
        ],
        "rationale": "Type hints improve readability.",
        "confidence": 0.9,
    }
)
COMPATIBLE_TRANSFORMATION_RESPONSE = ADD_TRANSFORMATION_RESPONSE

ADD_REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "refactor add"}
SUB_REQUEST = {"target_cells": [2], "transformation_type": REFACTOR, "instructions": "refactor sub"}
REQUEST = ADD_REQUEST

HAPPY_SCRIPT = [
    make_response(ANALYSIS_RESPONSE),
    make_response(CANDIDATE_RESPONSE),
    make_response(ADD_INPUT_SCHEMA_RESPONSE),
    make_response(ADD_OUTPUT_SCHEMA_RESPONSE),
    make_response(ADD_TEST_GENERATION_RESPONSE),
    make_response(SUB_INPUT_SCHEMA_RESPONSE),
    make_response(SUB_OUTPUT_SCHEMA_RESPONSE),
    make_response(SUB_TEST_GENERATION_RESPONSE),
    make_response(ADD_TRANSFORMATION_RESPONSE),
    make_response(EMPTY_FINDINGS_RESPONSE),
]


def _register_candidates_and_tests(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    add_candidate, sub_candidate = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(add_candidate.candidate_id)
    env["output_schema"].infer(add_candidate.candidate_id)
    env["test_generation"].generate(add_candidate.candidate_id)
    env["input_schema"].infer(sub_candidate.candidate_id)
    env["output_schema"].infer(sub_candidate.candidate_id)
    env["test_generation"].generate(sub_candidate.candidate_id)
    return analysis, add_candidate, sub_candidate


def _gate_passed_execution(env, request=ADD_REQUEST, registered=False):
    if not registered:
        _register_candidates_and_tests(env)
    plan = env["transformation"].plan("nb-1", request)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    execution = env["execution"].apply(diff.diff_id)
    env["verification"].verify(execution.execution_id)
    env["regression"].analyze(execution.execution_id)
    env["gate"].evaluate(execution.execution_id)
    return execution


def test_release_preparation_succeeds_once_all_gates_pass():
    env = build_env(list(HAPPY_SCRIPT))
    execution = _gate_passed_execution(env)

    release = env["release"].prepare(execution.execution_id)

    assert release.execution_id == execution.execution_id
    assert release.status == PREPARED
    assert release.released_at is None
    assert release.version


def test_gate_enforcement_blocks_preparation():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(COMPATIBLE_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan = env["transformation"].plan("nb-1", REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    execution = env["execution"].apply(diff.diff_id)
    # Gates never evaluated at all.

    with pytest.raises(GatesNotEvaluatedError):
        env["release"].prepare(execution.execution_id)

    # Gates evaluated, but verification/regression were never run -- both fail.
    env["gate"].evaluate(execution.execution_id)

    with pytest.raises(GatesNotPassedError):
        env["release"].prepare(execution.execution_id)


def test_version_is_created_and_increments_per_notebook():
    env = build_env(
        list(HAPPY_SCRIPT) + [make_response(SUB_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    _register_candidates_and_tests(env)
    first_execution = _gate_passed_execution(env, ADD_REQUEST, registered=True)
    first_release = env["release"].prepare(first_execution.execution_id)

    assert first_release.version == "nb-1-v1"

    released = env["release"].release(first_release.release_id)
    assert released.version == first_release.version

    second_execution = _gate_passed_execution(env, SUB_REQUEST, registered=True)
    second_release = env["release"].prepare(second_execution.execution_id)

    assert second_release.version == "nb-1-v2"


def test_failed_preparation_leaves_nothing_to_release():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(COMPATIBLE_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan = env["transformation"].plan("nb-1", REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    execution = env["execution"].apply(diff.diff_id)
    env["gate"].evaluate(execution.execution_id)

    with pytest.raises(GatesNotPassedError):
        env["release"].prepare(execution.execution_id)

    with pytest.raises(UnknownReleaseError):
        env["release"].release(f"release-{execution.execution_id}-1")
    with pytest.raises(UnknownReleaseError):
        env["release"].status(f"release-{execution.execution_id}-1")


def test_release_records_are_immutable():
    env = build_env(list(HAPPY_SCRIPT))
    execution = _gate_passed_execution(env)
    prepared = env["release"].prepare(execution.execution_id)

    with pytest.raises(FrozenInstanceError):
        prepared.status = RELEASED

    released = env["release"].release(prepared.release_id)

    assert prepared.status == PREPARED
    assert prepared.released_at is None
    assert released.status == RELEASED
    assert released.release_id == prepared.release_id


def test_status_lifecycle_moves_from_prepared_to_released():
    env = build_env(list(HAPPY_SCRIPT))
    execution = _gate_passed_execution(env)
    release = env["release"].prepare(execution.execution_id)

    assert env["release"].status(release.release_id) == PREPARED
    assert env["release"].validate(release.release_id) is True

    env["release"].release(release.release_id)

    assert env["release"].status(release.release_id) == RELEASED

    with pytest.raises(ReleaseNotPreparedError):
        env["release"].release(release.release_id)
