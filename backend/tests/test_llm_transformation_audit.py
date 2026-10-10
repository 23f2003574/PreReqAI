import json

import pytest
from dataclasses import FrozenInstanceError

from backend.code_transformation import REFACTOR, LLMCodeTransformationService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.transformation_approval import LLMTransformationApprovalService
from backend.transformation_audit import (
    APPLIED,
    ROLLED_BACK,
    VERIFICATION_FAILED,
    VERIFIED,
    BrokenLifecycleLinkError,
    LLMTransformationAuditService,
    UnknownAuditError,
)
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_validation import LLMTransformationValidationService
from backend.transformation_verification import UnknownVerificationError


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


class FakeVerificationService:
    """A minimal stand-in exposing only what LLMTransformationAuditService calls."""

    def __init__(self, blocking_by_execution=None):
        self._blocking_by_execution = dict(blocking_by_execution or {})

    def blocking(self, execution_id):
        try:
            return self._blocking_by_execution[execution_id]
        except KeyError:
            raise UnknownVerificationError(execution_id)


def make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


def build_env(script, blocking_by_execution=None):
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
    verification_service = FakeVerificationService(blocking_by_execution)
    audit_service = LLMTransformationAuditService(
        transformation_service, diff_service, approval_service, execution_service, verification_service
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "transformation": transformation_service,
        "validation": validation_service,
        "diff": diff_service,
        "approval": approval_service,
        "execution": execution_service,
        "verification": verification_service,
        "audit": audit_service,
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


def _approved_execution(env, request, reviewer="alice"):
    plan = env["transformation"].plan("nb-1", request)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, reviewer)
    execution = env["execution"].apply(diff.diff_id)
    return plan, diff, execution


def test_lifecycle_linkage_is_validated():
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
    plan, diff, execution = _approved_execution(env, ADD_REQUEST)
    other_plan, _other_diff, _other_execution = _approved_execution(env, SUB_REQUEST)

    audit = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)

    assert audit.plan_id == plan.plan_id
    assert audit.diff_id == diff.diff_id
    assert audit.execution_id == execution.execution_id
    assert audit.reviewer == "alice"

    with pytest.raises(BrokenLifecycleLinkError):
        env["audit"].record(other_plan.plan_id, diff.diff_id, execution.execution_id)


def test_verification_outcome_is_reflected_in_status():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan, diff, execution = _approved_execution(env, ADD_REQUEST)

    unverified_audit = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)
    assert unverified_audit.status == APPLIED

    env["verification"]._blocking_by_execution[execution.execution_id] = False
    verified_audit = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)
    assert verified_audit.status == VERIFIED

    env["verification"]._blocking_by_execution[execution.execution_id] = True
    failed_audit = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)
    assert failed_audit.status == VERIFICATION_FAILED


def test_rollback_outcome_is_reflected_in_status():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan, diff, execution = _approved_execution(env, ADD_REQUEST)

    env["execution"].rollback(execution.execution_id)

    audit = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)

    assert audit.status == ROLLED_BACK


def test_notebook_history_spans_multiple_executions_in_order():
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
    add_plan, add_diff, add_execution = _approved_execution(env, ADD_REQUEST)
    sub_plan, sub_diff, sub_execution = _approved_execution(env, SUB_REQUEST)

    first = env["audit"].record(add_plan.plan_id, add_diff.diff_id, add_execution.execution_id)
    second = env["audit"].record(sub_plan.plan_id, sub_diff.diff_id, sub_execution.execution_id)

    history = env["audit"].history("nb-1")

    assert history == [first, second]
    assert env["audit"].history("nb-does-not-exist") == []


def test_audit_records_are_immutable_and_append_only():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan, diff, execution = _approved_execution(env, ADD_REQUEST)

    first = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)
    with pytest.raises(FrozenInstanceError):
        first.status = ROLLED_BACK

    env["verification"]._blocking_by_execution[execution.execution_id] = False
    second = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)

    assert first.status == APPLIED
    assert second.status == VERIFIED
    assert env["audit"].get(execution.execution_id) == second
    assert env["audit"].history("nb-1") == [first, second]

    with pytest.raises(UnknownAuditError):
        env["audit"].get("execution-never-recorded")


def test_reviewer_looking_like_a_secret_is_redacted():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan, diff, execution = _approved_execution(env, ADD_REQUEST, reviewer="sk-abcdEFGH12345678ijkl")

    audit = env["audit"].record(plan.plan_id, diff.diff_id, execution.execution_id)

    assert audit.reviewer == "[REDACTED]"
