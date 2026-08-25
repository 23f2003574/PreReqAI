import json

import pytest

from backend.code_transformation import REFACTOR, LLMCodeTransformationService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.transformation_validation import (
    LLMTransformationValidationService,
    UnknownValidationError,
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
    transformation_service = LLMCodeTransformationService(
        notebook_analysis_service, orchestration_service, context_service
    )
    validation_service = LLMTransformationValidationService(
        transformation_service, notebook_analysis_service, orchestration_service, context_service
    )
    return notebook_analysis_service, transformation_service, validation_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def helper():\n    return 1"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "helper", "cell_index": 1}, {"name": "add", "cell_index": 2}],
        "dependencies": [],
    }
)

SMALLER_NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def helper():\n    return 1"},
    ],
}
SMALLER_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "helper", "cell_index": 1}], "dependencies": []}
)

EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})


def valid_change_response():
    return json.dumps(
        {
            "changes": [
                {
                    "cell_index": 2,
                    "description": "Add type hints.",
                    "proposed_source": "def add(a: int, b: int) -> int:\n    return a + b",
                }
            ],
            "rationale": "Type hints improve readability.",
            "confidence": 0.9,
        }
    )


def symbol_conflict_change_response():
    return json.dumps(
        {
            "changes": [
                {
                    "cell_index": 2,
                    "description": "Rename add to helper by mistake.",
                    "proposed_source": "def helper():\n    return 2",
                }
            ],
            "rationale": "Consolidate naming.",
            "confidence": 0.6,
        }
    )


def conflicting_changes_response():
    return json.dumps(
        {
            "changes": [
                {
                    "cell_index": 1,
                    "description": "Rename helper to shared.",
                    "proposed_source": "def shared():\n    return 1",
                },
                {
                    "cell_index": 2,
                    "description": "Rename add to shared too.",
                    "proposed_source": "def shared():\n    return 2",
                },
            ],
            "rationale": "Consolidate two helpers under one name.",
            "confidence": 0.5,
        }
    )


REQUEST_CELL_2 = {"target_cells": [2], "transformation_type": REFACTOR, "instructions": "add type hints"}
REQUEST_CELLS_1_2 = {
    "target_cells": [1, 2],
    "transformation_type": REFACTOR,
    "instructions": "consolidate helpers",
}


def test_valid_plan_has_no_blocking_findings():
    notebook_analysis, transformation, validation = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(valid_change_response()), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST_CELL_2)

    result = validation.validate(plan.plan_id)

    assert result.plan_id == plan.plan_id
    assert result.valid is True
    assert result.findings == []
    assert validation.blocking(plan.plan_id) is False
    assert validation.findings(plan.plan_id) == []


def test_unknown_cell_is_a_blocking_finding():
    notebook_analysis, transformation, validation = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(valid_change_response()),
            make_response(SMALLER_ANALYSIS_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST_CELL_2)

    notebook_analysis.analyze(SMALLER_NOTEBOOK)

    result = validation.validate(plan.plan_id)

    assert result.valid is False
    categories = {finding["category"] for finding in result.findings}
    assert "UNKNOWN_CELL" in categories
    assert all(finding["blocking"] for finding in result.findings if finding["category"] == "UNKNOWN_CELL")


def test_symbol_conflict_with_rest_of_notebook_is_blocking():
    notebook_analysis, transformation, validation = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(symbol_conflict_change_response()),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST_CELL_2)

    result = validation.validate(plan.plan_id)

    assert result.valid is False
    categories = {finding["category"] for finding in result.findings}
    assert "SYMBOL_CONFLICT" in categories


def test_conflicting_changes_within_the_same_plan_are_blocking():
    notebook_analysis, transformation, validation = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(conflicting_changes_response()),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST_CELLS_1_2)

    result = validation.validate(plan.plan_id)

    assert result.valid is False
    categories = {finding["category"] for finding in result.findings}
    assert "CONFLICTING_TRANSFORMATION" in categories


def test_llm_reported_blocking_finding_makes_the_plan_invalid():
    llm_blocking_response = json.dumps(
        {
            "findings": [
                {
                    "category": "UNSAFE_ASSUMPTION",
                    "target": "2",
                    "message": "Type hints assume callers never pass floats.",
                    "blocking": True,
                }
            ]
        }
    )
    notebook_analysis, transformation, validation = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(valid_change_response()), make_response(llm_blocking_response)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST_CELL_2)

    result = validation.validate(plan.plan_id)

    assert result.valid is False
    assert validation.blocking(plan.plan_id) is True
    assert any(f["category"] == "UNSAFE_ASSUMPTION" for f in result.findings)


def test_validation_result_is_stored_and_readable_only_after_validate():
    notebook_analysis, transformation, validation = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(valid_change_response()), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST_CELL_2)

    with pytest.raises(UnknownValidationError):
        validation.findings(plan.plan_id)
    with pytest.raises(UnknownValidationError):
        validation.blocking(plan.plan_id)

    result = validation.validate(plan.plan_id)

    assert result.validation_id
    assert result.checked_at is not None
    assert result.plan_id == plan.plan_id
    # Re-validating never mutates the plan itself.
    assert transformation.get(plan.plan_id) == plan
