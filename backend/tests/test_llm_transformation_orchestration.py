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
from backend.transformation_gate import LLMTransformationGateService
from backend.transformation_orchestration import (
    APPLIED,
    READY_FOR_RELEASE,
    REJECTED,
    RELEASED,
    ROLLED_BACK,
    LLMCodeTransformationOrchestrationService,
)
from backend.transformation_regression import LLMTransformationRegressionService
from backend.transformation_release import RELEASED as RELEASE_RELEASED
from backend.transformation_release import LLMTransformationReleaseService
from backend.transformation_rollback import LLMTransformationRollbackService
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
    rollback_service = LLMTransformationRollbackService(execution_service, diff_service, transformation_service)
    orchestration = LLMCodeTransformationOrchestrationService(
        transformation_service,
        validation_service,
        diff_service,
        approval_service,
        execution_service,
        verification_service,
        regression_service,
        gate_service,
        release_service,
        rollback_service,
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "test_generation": test_generation_service,
        "transformation": transformation_service,
        "diff": diff_service,
        "approval": approval_service,
        "execution": execution_service,
        "release": release_service,
        "orchestration": orchestration,
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
DROP_PARAM_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Drop the unused b parameter.",
                "proposed_source": "def add(a: int) -> dict:\n    return {'sum': a}",
            }
        ],
        "rationale": "b was never used elsewhere.",
        "confidence": 0.6,
    }
)
OFF_BY_ONE_TRANSFORMATION_RESPONSE = json.dumps(
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

REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "refactor add", "reviewer": "alice"}


def _register_candidate_and_tests(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    env["test_generation"].generate(candidate.candidate_id)


def test_successful_transformation_reaches_applied():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(COMPATIBLE_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)

    decision = env["orchestration"].transform("nb-1", REQUEST)

    assert decision.status == APPLIED
    assert decision.execution_id is not None
    assert decision.release_id is None


def test_approval_rejection_stops_before_any_execution():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(COMPATIBLE_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    rejecting_request = dict(REQUEST, approved=False, reason="not needed right now")

    decision = env["orchestration"].transform("nb-1", rejecting_request)

    assert decision.status == REJECTED
    assert decision.execution_id is None
    assert decision.reason == "not needed right now"


def test_verification_failure_triggers_automatic_rollback():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(DROP_PARAM_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    _register_candidate_and_tests(env)
    applied = env["orchestration"].transform("nb-1", REQUEST)

    decision = env["orchestration"].review(applied.execution_id)

    assert decision.status == ROLLED_BACK
    assert decision.reason == "verification failed"
    live = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source
    assert live == "def add(a, b):\n    return {'sum': a + b}"


def test_regression_failure_triggers_automatic_rollback():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(OFF_BY_ONE_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    _register_candidate_and_tests(env)
    applied = env["orchestration"].transform("nb-1", REQUEST)

    decision = env["orchestration"].review(applied.execution_id)

    assert decision.status == ROLLED_BACK
    assert decision.reason == "regression detected"


def test_gate_failure_triggers_automatic_rollback():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(TEST_GENERATION_RESPONSE),
            make_response(DANGEROUS_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    _register_candidate_and_tests(env)
    applied = env["orchestration"].transform("nb-1", REQUEST)

    decision = env["orchestration"].review(applied.execution_id)

    assert decision.status == ROLLED_BACK
    assert decision.reason.startswith("gates failed:")
    assert "SECURITY" in decision.reason


def test_successful_release_after_all_checks_pass():
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
    applied = env["orchestration"].transform("nb-1", REQUEST)
    reviewed = env["orchestration"].review(applied.execution_id)
    assert reviewed.status == READY_FOR_RELEASE

    decision = env["orchestration"].release(applied.execution_id)

    assert decision.status == RELEASED
    assert decision.release_id is not None
    assert env["release"].status(decision.release_id) == RELEASE_RELEASED


def test_manual_rollback_path_restores_source():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(COMPATIBLE_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    applied = env["orchestration"].transform("nb-1", REQUEST)

    decision = env["orchestration"].rollback(applied.execution_id)

    assert decision.status == ROLLED_BACK
    live = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source
    assert live == "def add(a, b):\n    return {'sum': a + b}"


def test_decision_is_one_deterministic_record_updated_in_place():
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
    applied = env["orchestration"].transform("nb-1", REQUEST)

    assert env["orchestration"].decision(applied.execution_id) == applied
    assert env["orchestration"].decision(applied.execution_id) == env["orchestration"].decision(applied.execution_id)

    reviewed = env["orchestration"].review(applied.execution_id)

    assert env["orchestration"].decision(applied.execution_id) == reviewed
    assert env["orchestration"].decision(applied.execution_id).status == READY_FOR_RELEASE
