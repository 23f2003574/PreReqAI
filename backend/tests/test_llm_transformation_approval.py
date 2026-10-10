import json

import pytest

from backend.code_transformation import REFACTOR, LLMCodeTransformationService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.transformation_approval import (
    APPROVED,
    PENDING,
    REJECTED,
    DiffNotValidatedError,
    DuplicateDecisionError,
    LLMTransformationApprovalService,
    MissingReasonError,
    MissingReviewerError,
)
from backend.transformation_diff import LLMTransformationDiffService
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
    return notebook_analysis_service, transformation_service, validation_service, diff_service, approval_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "add", "cell_index": 1}], "dependencies": []}
)

CHANGED_SOURCE_NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b + 1"},
    ],
}
CHANGED_SOURCE_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "add", "cell_index": 1}], "dependencies": []}
)

EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})
TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Add type hints.",
                "proposed_source": "def add(a: int, b: int) -> int:\n    return a + b",
            }
        ],
        "rationale": "Type hints improve readability.",
        "confidence": 0.9,
    }
)

REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "add type hints"}


def _approved_diff(script_extra=()):
    notebook_analysis, transformation, validation, diff_service, approval = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
        + list(script_extra)
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST)
    validation.validate(plan.plan_id)
    diff = diff_service.generate(plan.plan_id)
    return notebook_analysis, diff_service, approval, diff


def test_approve_records_an_immutable_approved_decision():
    notebook_analysis, diff_service, approval, diff = _approved_diff()

    decision = approval.approve(diff.diff_id, "alice")

    assert decision.diff_id == diff.diff_id
    assert decision.reviewer == "alice"
    assert decision.status == APPROVED
    assert decision.reason is None
    assert decision.approved_at is not None
    assert approval.status(diff.diff_id) == APPROVED


def test_reject_requires_a_reason_and_records_it():
    notebook_analysis, diff_service, approval, diff = _approved_diff()

    with pytest.raises(MissingReasonError):
        approval.reject(diff.diff_id, "bob", "")

    decision = approval.reject(diff.diff_id, "bob", "Breaks backward compatibility.")

    assert decision.status == REJECTED
    assert decision.reason == "Breaks backward compatibility."
    assert approval.status(diff.diff_id) == REJECTED


def test_decision_is_blocked_when_the_diff_has_gone_stale():
    notebook_analysis, diff_service, approval, diff = _approved_diff(
        [make_response(CHANGED_SOURCE_ANALYSIS_RESPONSE)]
    )

    notebook_analysis.analyze(CHANGED_SOURCE_NOTEBOOK)

    with pytest.raises(DiffNotValidatedError):
        approval.approve(diff.diff_id, "alice")


def test_reviewer_is_required_for_both_approve_and_reject():
    notebook_analysis, diff_service, approval, diff = _approved_diff()

    with pytest.raises(MissingReviewerError):
        approval.approve(diff.diff_id, "")
    with pytest.raises(MissingReviewerError):
        approval.reject(diff.diff_id, None, "not good")


def test_duplicate_decision_on_the_same_diff_is_rejected():
    notebook_analysis, diff_service, approval, diff = _approved_diff()

    approval.approve(diff.diff_id, "alice")

    with pytest.raises(DuplicateDecisionError):
        approval.approve(diff.diff_id, "alice")
    with pytest.raises(DuplicateDecisionError):
        approval.reject(diff.diff_id, "bob", "changed my mind")


def test_status_and_history_reflect_the_recorded_decision():
    notebook_analysis, diff_service, approval, diff = _approved_diff()

    assert approval.status(diff.diff_id) == PENDING
    assert approval.history(diff.diff_id) == ()

    decision = approval.approve(diff.diff_id, "alice")

    assert approval.status(diff.diff_id) == APPROVED
    assert approval.history(diff.diff_id) == (decision,)
