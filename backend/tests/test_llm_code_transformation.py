import json

import pytest

from backend.code_transformation import (
    ADAPT,
    FIX,
    REFACTOR,
    InvalidTransformationRequestError,
    LLMCodeTransformationService,
    MalformedTransformationResponseError,
    UnknownTransformationPlanError,
    UnresolvableCellReferenceError,
)
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService


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
    return notebook_analysis_service, transformation_service


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

SMALLER_NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [{"cell_type": "markdown", "source": "# Intro"}],
}
SMALLER_ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": [], "dependencies": []})

TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Add type hints and a docstring.",
                "proposed_source": "def add(a: int, b: int) -> int:\n    \"\"\"Add two numbers.\"\"\"\n    return a + b",
            }
        ],
        "rationale": "Type hints improve readability and catch misuse earlier.",
        "confidence": 0.85,
    }
)

REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "add type hints"}


def test_plan_generation_produces_a_deterministic_reviewable_plan():
    notebook_analysis, service = build_env([make_response(ANALYSIS_RESPONSE), make_response(TRANSFORMATION_RESPONSE)])
    notebook_analysis.analyze(NOTEBOOK)

    plan = service.plan("nb-1", REQUEST)

    assert plan.notebook_id == "nb-1"
    assert plan.target_cells == (1,)
    assert plan.transformation_type == REFACTOR
    assert len(plan.changes) == 1
    assert plan.changes[0]["cell_index"] == 1
    assert plan.changes[0]["description"] == "Add type hints and a docstring."
    assert plan.confidence == 0.85
    assert plan.rationale

    # Re-fetching by id returns the exact same stored plan -- deterministic and reviewable.
    assert service.get(plan.plan_id) == plan

    with pytest.raises(UnknownTransformationPlanError):
        service.get("nonexistent-plan")


def test_invalid_target_cell_is_rejected_before_any_llm_call():
    notebook_analysis, service = build_env([make_response(ANALYSIS_RESPONSE)])
    notebook_analysis.analyze(NOTEBOOK)

    bad_request = {"target_cells": [99], "transformation_type": FIX, "instructions": "fix the bug"}

    with pytest.raises(UnresolvableCellReferenceError):
        service.plan("nb-1", bad_request)


def test_transformation_type_is_validated():
    notebook_analysis, service = build_env([make_response(ANALYSIS_RESPONSE)])
    notebook_analysis.analyze(NOTEBOOK)

    bad_request = {"target_cells": [1], "transformation_type": "REWRITE", "instructions": "do something"}

    with pytest.raises(InvalidTransformationRequestError):
        service.plan("nb-1", bad_request)


def test_llm_response_change_outside_target_cells_is_rejected():
    off_target_response = json.dumps(
        {
            "changes": [{"cell_index": 0, "description": "oops", "proposed_source": "# nope"}],
            "rationale": "irrelevant",
            "confidence": 0.5,
        }
    )
    notebook_analysis, service = build_env([make_response(ANALYSIS_RESPONSE), make_response(off_target_response)])
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(UnresolvableCellReferenceError):
        service.plan("nb-1", REQUEST)


def test_validate_detects_cells_removed_since_the_plan_was_built():
    notebook_analysis, service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(SMALLER_ANALYSIS_RESPONSE),
        ]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = service.plan("nb-1", REQUEST)

    assert service.validate(plan.plan_id) is True

    # The notebook is re-analyzed and cell 1 no longer exists -- the plan is now stale.
    notebook_analysis.analyze(SMALLER_NOTEBOOK)

    with pytest.raises(UnresolvableCellReferenceError):
        service.validate(plan.plan_id)


def test_preview_pairs_each_change_with_the_cells_current_source():
    notebook_analysis, service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(TRANSFORMATION_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = service.plan("nb-1", REQUEST)

    preview = service.preview(plan.plan_id)

    assert len(preview) == 1
    entry = preview[0]
    assert entry["cell_index"] == 1
    assert entry["original_source"] == "def add(a, b):\n    return a + b"
    assert entry["proposed_source"] == plan.changes[0]["proposed_source"]
    assert entry["description"] == plan.changes[0]["description"]


def test_planning_and_previewing_never_mutate_the_notebook_source():
    notebook_analysis, service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(TRANSFORMATION_RESPONSE)]
    )
    analysis = notebook_analysis.analyze(NOTEBOOK)
    original_source = analysis.cells[1].source

    plan = service.plan("nb-1", REQUEST)
    service.preview(plan.plan_id)

    current_analysis = notebook_analysis.get_by_notebook("nb-1")
    assert current_analysis.cells[1].source == original_source
    assert current_analysis is analysis
    # The proposal is only ever recorded on the plan, never written back onto the cell.
    assert current_analysis.cells[1].source != plan.changes[0]["proposed_source"]


def test_malformed_llm_response_is_rejected():
    notebook_analysis, service = build_env([make_response(ANALYSIS_RESPONSE), make_response("not json")])
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(MalformedTransformationResponseError):
        service.plan("nb-1", REQUEST)
