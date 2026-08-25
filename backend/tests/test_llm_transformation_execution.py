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
from backend.transformation_execution import (
    ROLLED_BACK,
    SUCCEEDED,
    AlreadyAppliedError,
    ApplicationNotValidatedError,
    DiffNotApprovedError,
    InvalidRollbackStateError,
    LLMTransformationExecutionService,
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
    return {
        "notebook_analysis": notebook_analysis_service,
        "transformation": transformation_service,
        "validation": validation_service,
        "diff": diff_service,
        "approval": approval_service,
        "execution": execution_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
        {"cell_type": "code", "source": "def sub(a, b):\n    return a - b"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "add", "cell_index": 1}, {"name": "sub", "cell_index": 2}],
        "dependencies": [],
    }
)

ONE_CELL_ADD_SOURCE = "def add(a: int, b: int) -> int:\n    return a + b"
ONE_CELL_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {"cell_index": 1, "description": "Add type hints.", "proposed_source": ONE_CELL_ADD_SOURCE}
        ],
        "rationale": "Type hints improve readability.",
        "confidence": 0.9,
    }
)

TWO_CELL_SUB_SOURCE = "def sub(a: int, b: int) -> int:\n    return a - b"
TWO_CELL_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {"cell_index": 1, "description": "Add type hints to add.", "proposed_source": ONE_CELL_ADD_SOURCE},
            {"cell_index": 2, "description": "Add type hints to sub.", "proposed_source": TWO_CELL_SUB_SOURCE},
        ],
        "rationale": "Type hints improve readability.",
        "confidence": 0.9,
    }
)

DRIFTED_CELL_1_NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b  # edited by someone else"},
        {"cell_type": "code", "source": "def sub(a, b):\n    return a - b"},
    ],
}
DRIFTED_ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "add", "cell_index": 1}, {"name": "sub", "cell_index": 2}],
        "dependencies": [],
    }
)

EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})

ONE_CELL_REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "add type hints"}
TWO_CELL_REQUEST = {
    "target_cells": [1, 2],
    "transformation_type": REFACTOR,
    "instructions": "add type hints",
}


def _approved_diff(env, request, transformation_response, notebook=NOTEBOOK):
    env["notebook_analysis"].analyze(notebook)
    plan = env["transformation"].plan(notebook["notebook_id"], request)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    return diff


def test_successful_application_mutates_the_target_cell_source():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(ONE_CELL_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    diff = _approved_diff(env, ONE_CELL_REQUEST, ONE_CELL_TRANSFORMATION_RESPONSE)

    execution = env["execution"].apply(diff.diff_id)

    assert execution.status == SUCCEEDED
    assert env["execution"].status(execution.execution_id) == SUCCEEDED
    live_cell = env["notebook_analysis"].get_by_notebook("nb-1").cells[1]
    assert live_cell.source == ONE_CELL_ADD_SOURCE


def test_apply_requires_an_approved_diff():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(ONE_CELL_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan = env["transformation"].plan("nb-1", ONE_CELL_REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    # Deliberately never approved.

    with pytest.raises(DiffNotApprovedError):
        env["execution"].apply(diff.diff_id)

    live_cell = env["notebook_analysis"].get_by_notebook("nb-1").cells[1]
    assert live_cell.source == "def add(a, b):\n    return a + b"


def test_apply_is_atomic_when_one_of_several_target_cells_has_drifted():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TWO_CELL_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
            make_response(DRIFTED_ANALYSIS_RESPONSE),
        ]
    )
    diff = _approved_diff(env, TWO_CELL_REQUEST, TWO_CELL_TRANSFORMATION_RESPONSE)

    # Someone else edits cell 1 after the diff was approved -- cell 2 is untouched.
    env["notebook_analysis"].analyze(DRIFTED_CELL_1_NOTEBOOK)

    with pytest.raises(ApplicationNotValidatedError):
        env["execution"].apply(diff.diff_id)

    live = env["notebook_analysis"].get_by_notebook("nb-1")
    assert live.cells[1].source == "def add(a, b):\n    return a + b  # edited by someone else"
    assert live.cells[2].source == "def sub(a, b):\n    return a - b"


def test_rollback_restores_original_source_and_blocks_a_second_rollback():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(ONE_CELL_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    diff = _approved_diff(env, ONE_CELL_REQUEST, ONE_CELL_TRANSFORMATION_RESPONSE)
    execution = env["execution"].apply(diff.diff_id)

    rolled_back = env["execution"].rollback(execution.execution_id)

    assert rolled_back.status == ROLLED_BACK
    assert env["execution"].status(execution.execution_id) == ROLLED_BACK
    live_cell = env["notebook_analysis"].get_by_notebook("nb-1").cells[1]
    assert live_cell.source == "def add(a, b):\n    return a + b"

    with pytest.raises(InvalidRollbackStateError):
        env["execution"].rollback(execution.execution_id)


def test_affected_cells_are_recorded_on_the_execution():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TWO_CELL_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    diff = _approved_diff(env, TWO_CELL_REQUEST, TWO_CELL_TRANSFORMATION_RESPONSE)

    execution = env["execution"].apply(diff.diff_id)

    assert {c["cell_index"] for c in execution.applied_cells} == {1, 2}
    by_cell = {c["cell_index"]: c for c in execution.applied_cells}
    assert by_cell[1]["original_source"] == "def add(a, b):\n    return a + b"
    assert by_cell[1]["applied_source"] == ONE_CELL_ADD_SOURCE
    assert by_cell[2]["original_source"] == "def sub(a, b):\n    return a - b"
    assert by_cell[2]["applied_source"] == TWO_CELL_SUB_SOURCE


def test_duplicate_application_of_the_same_diff_is_rejected():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(ONE_CELL_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    diff = _approved_diff(env, ONE_CELL_REQUEST, ONE_CELL_TRANSFORMATION_RESPONSE)

    env["execution"].apply(diff.diff_id)

    with pytest.raises(AlreadyAppliedError):
        env["execution"].apply(diff.diff_id)
