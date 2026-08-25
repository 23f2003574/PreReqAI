import json
from datetime import datetime, timezone

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
from backend.transformation_execution import (
    SUCCEEDED,
    LLMTransformationExecution,
    LLMTransformationExecutionService,
    UnknownExecutionError,
)
from backend.transformation_validation import LLMTransformationValidationService
from backend.transformation_verification import (
    ExecutionNotAppliedError,
    LLMTransformationVerificationService,
    UnknownVerificationError,
)


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
                "description": "Drop the unused b parameter.",
                "proposed_source": "def add(a: int) -> dict:\n    return {'sum': a}",
            }
        ],
        "rationale": "b was never used elsewhere.",
        "confidence": 0.6,
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
    candidates = env["api_candidate"].analyze(analysis.analysis_id)
    candidate = candidates[0]
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    env["test_generation"].generate(candidate.candidate_id)
    return env


def _applied_execution(env, notebook_id="nb-1"):
    plan = env["transformation"].plan(notebook_id, REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    return env["execution"].apply(diff.diff_id)


def test_successful_verification_passes_syntax_and_compatible_tests():
    env = _happy_env(COMPATIBLE_TRANSFORMATION_RESPONSE)
    execution = _applied_execution(env)

    result = env["verification"].verify(execution.execution_id)

    assert result.execution_id == execution.execution_id
    assert result.syntax_valid is True
    assert result.tests_passed is True
    assert env["verification"].blocking(execution.execution_id) is False


def test_syntax_failure_is_caught_before_any_test_runs():
    now = datetime.now(timezone.utc)
    broken_execution = LLMTransformationExecution(
        execution_id="execution-broken-1",
        diff_id="diff-broken-1",
        status=SUCCEEDED,
        applied_cells=(
            {
                "cell_index": 1,
                "original_source": "def add(a, b):\n    return {'sum': a + b}",
                "applied_source": "def add(a, b)\n    return {'sum': a + b}",
            },
        ),
        created_at=now,
        completed_at=now,
    )

    class FakeExecutionService:
        def get(self, execution_id):
            if execution_id != broken_execution.execution_id:
                raise UnknownExecutionError(execution_id)
            return broken_execution

    verification_service = LLMTransformationVerificationService(
        FakeExecutionService(), None, None, None, None
    )

    result = verification_service.verify(broken_execution.execution_id)

    assert result.syntax_valid is False
    assert result.tests_passed is False
    categories = {f["category"] for f in result.findings}
    assert "SYNTAX_ERROR" in categories
    assert verification_service.blocking(broken_execution.execution_id) is True


def test_transformation_that_breaks_an_existing_test_fails_verification():
    env = _happy_env(BREAKING_TRANSFORMATION_RESPONSE)
    execution = _applied_execution(env)

    result = env["verification"].verify(execution.execution_id)

    assert result.syntax_valid is True
    assert result.tests_passed is False
    categories = {f["category"] for f in result.findings}
    assert "TEST_FAILURE" in categories


def test_blocking_reflects_any_blocking_finding():
    env = _happy_env(BREAKING_TRANSFORMATION_RESPONSE)
    execution = _applied_execution(env)
    env["verification"].verify(execution.execution_id)

    assert env["verification"].blocking(execution.execution_id) is True


def test_only_an_applied_execution_can_be_verified():
    env = _happy_env(COMPATIBLE_TRANSFORMATION_RESPONSE)
    execution = _applied_execution(env)
    env["execution"].rollback(execution.execution_id)

    with pytest.raises(ExecutionNotAppliedError):
        env["verification"].verify(execution.execution_id)


def test_verification_state_is_stored_and_readable_only_after_verify():
    env = _happy_env(COMPATIBLE_TRANSFORMATION_RESPONSE)
    execution = _applied_execution(env)

    with pytest.raises(UnknownVerificationError):
        env["verification"].syntax(execution.execution_id)
    with pytest.raises(UnknownVerificationError):
        env["verification"].tests(execution.execution_id)
    with pytest.raises(UnknownVerificationError):
        env["verification"].blocking(execution.execution_id)

    result = env["verification"].verify(execution.execution_id)

    assert env["verification"].syntax(execution.execution_id) == result.syntax_valid
    assert env["verification"].tests(execution.execution_id) == result.tests_passed
    assert result.verification_id
    assert result.verified_at is not None
