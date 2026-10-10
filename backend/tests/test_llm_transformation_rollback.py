import json

import pytest

from backend.code_transformation import REFACTOR, LLMCodeTransformationService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.transformation_approval import LLMTransformationApprovalService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import LLMTransformationExecutionService, UnknownExecutionError
from backend.transformation_rollback import (
    RESTORED,
    AlreadyRolledBackError,
    ExecutionNotAppliedError,
    LLMTransformationRollbackService,
    MissingReasonError,
    UnknownRollbackError,
)
from backend.transformation_validation import LLMTransformationValidationService


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
    rollback_service = LLMTransformationRollbackService(execution_service, diff_service, transformation_service)

    return {
        "notebook_analysis": notebook_analysis_service,
        "transformation": transformation_service,
        "validation": validation_service,
        "diff": diff_service,
        "approval": approval_service,
        "execution": execution_service,
        "rollback": rollback_service,
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
EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})

ADD_REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "add type hints"}
SUB_REQUEST = {"target_cells": [2], "transformation_type": REFACTOR, "instructions": "add type hints"}


def _applied_execution(env, request):
    plan = env["transformation"].plan("nb-1", request)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    return env["execution"].apply(diff.diff_id)


def test_successful_rollback_restores_status_and_reason():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    execution = _applied_execution(env, ADD_REQUEST)

    record = env["rollback"].rollback(execution.execution_id, "verification found a regression")

    assert record.execution_id == execution.execution_id
    assert record.reason == "verification found a regression"
    assert record.status == RESTORED
    assert record.restored_at is not None
    assert env["rollback"].status(record.rollback_id) == RESTORED


def test_rollback_restores_the_original_source_snapshot():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    execution = _applied_execution(env, ADD_REQUEST)

    live_before_rollback = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source
    assert live_before_rollback == "def add(a: int, b: int) -> dict:\n    return {'sum': a + b}"

    env["rollback"].rollback(execution.execution_id, "regression detected")

    live_after_rollback = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source
    assert live_after_rollback == "def add(a, b):\n    return {'sum': a + b}"


def test_a_rejected_rollback_attempt_leaves_source_untouched():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    execution = _applied_execution(env, ADD_REQUEST)

    with pytest.raises(MissingReasonError):
        env["rollback"].rollback(execution.execution_id, "")

    live = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source
    assert live == "def add(a: int, b: int) -> dict:\n    return {'sum': a + b}"


def test_duplicate_rollback_is_rejected():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    execution = _applied_execution(env, ADD_REQUEST)

    env["rollback"].rollback(execution.execution_id, "first rollback")

    with pytest.raises(AlreadyRolledBackError):
        env["rollback"].rollback(execution.execution_id, "second attempt")


def test_only_an_applied_execution_can_be_rolled_back():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    execution = _applied_execution(env, ADD_REQUEST)
    # Rolled back directly through the underlying Commit #5 service, bypassing this commit's service.
    env["execution"].rollback(execution.execution_id)

    with pytest.raises(ExecutionNotAppliedError):
        env["rollback"].rollback(execution.execution_id, "already restored elsewhere")


def test_invalid_execution_id_raises():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    _applied_execution(env, ADD_REQUEST)

    with pytest.raises(UnknownExecutionError):
        env["rollback"].rollback("execution-never-created", "n/a")

    with pytest.raises(UnknownRollbackError):
        env["rollback"].status("rollback-never-created")


def test_rollback_history_is_scoped_to_the_notebook():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(ADD_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
            make_response(SUB_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    add_execution = _applied_execution(env, ADD_REQUEST)
    sub_execution = _applied_execution(env, SUB_REQUEST)

    first = env["rollback"].rollback(add_execution.execution_id, "regression on add")
    second = env["rollback"].rollback(sub_execution.execution_id, "regression on sub")

    history = env["rollback"].history("nb-1")

    assert history == [first, second]
    assert env["rollback"].history("nb-does-not-exist") == []
