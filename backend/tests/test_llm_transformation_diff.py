import json

import pytest

from backend.code_transformation import REFACTOR, LLMCodeTransformationService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.transformation_diff import (
    LLMTransformationDiffService,
    PlanNotValidError,
    StaleDiffError,
    UnmappedChangeError,
    UnvalidatedPlanError,
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
    return notebook_analysis_service, transformation_service, validation_service, diff_service


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

RESOURCE_NOTEBOOK = {
    "notebook_id": "nb-2",
    "cells": [
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
        {"cell_type": "code", "source": "def sub(a, b):\n    return a - b"},
    ],
}
RESOURCE_ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "add", "cell_index": 0}, {"name": "sub", "cell_index": 1}],
        "dependencies": [],
    }
)

SMALLER_NOTEBOOK = {"notebook_id": "nb-1", "cells": [{"cell_type": "markdown", "source": "# Intro"}]}
SMALLER_ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": [], "dependencies": []})

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
BLOCKING_FINDINGS_RESPONSE = json.dumps(
    {"findings": [{"category": "UNSAFE", "target": "1", "message": "risky", "blocking": True}]}
)

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

TWO_CELL_TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 0,
                "description": "Add type hints to add.",
                "proposed_source": "def add(a: int, b: int) -> int:\n    return a + b",
            },
            {
                "cell_index": 1,
                "description": "Add type hints to sub.",
                "proposed_source": "def sub(a: int, b: int) -> int:\n    return a - b",
            },
        ],
        "rationale": "Type hints improve readability.",
        "confidence": 0.9,
    }
)

REQUEST = {"target_cells": [1], "transformation_type": REFACTOR, "instructions": "add type hints"}
TWO_CELL_REQUEST = {
    "target_cells": [0, 1],
    "transformation_type": REFACTOR,
    "instructions": "add type hints",
}


def _validated_plan(notebook_analysis, transformation, validation, notebook, request):
    notebook_analysis.analyze(notebook)
    plan = transformation.plan(notebook["notebook_id"], request)
    validation.validate(plan.plan_id)
    return plan


def test_diff_generation_produces_a_unified_diff_per_change():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    plan = _validated_plan(notebook_analysis, transformation, validation, NOTEBOOK, REQUEST)

    diff = diff_service.generate(plan.plan_id)

    assert diff.plan_id == plan.plan_id
    assert len(diff.changes) == 1
    entry = diff.changes[0]
    assert entry["cell_index"] == 1
    assert "-def add(a, b):" in entry["unified_diff"]
    assert "+def add(a: int, b: int) -> int:" in entry["unified_diff"]
    assert diff.additions == entry["additions"] > 0
    assert diff.deletions == entry["deletions"] > 0
    assert diff_service.get(diff.diff_id) == diff


def test_every_planned_change_maps_to_exactly_one_diff_entry():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [
            make_response(RESOURCE_ANALYSIS_RESPONSE),
            make_response(TWO_CELL_TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    plan = _validated_plan(
        notebook_analysis, transformation, validation, RESOURCE_NOTEBOOK, TWO_CELL_REQUEST
    )

    diff = diff_service.generate(plan.plan_id)

    assert len(diff.changes) == len(plan.changes)
    assert {c["cell_index"] for c in diff.changes} == {c["cell_index"] for c in plan.changes}
    for planned, diffed in zip(plan.changes, diff.changes):
        assert planned["cell_index"] == diffed["cell_index"]
        assert planned["description"] == diffed["description"]
        assert planned["proposed_source"] == diffed["proposed_source"]


def test_diff_preserves_the_original_source_unaltered():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    plan = _validated_plan(notebook_analysis, transformation, validation, NOTEBOOK, REQUEST)

    diff = diff_service.generate(plan.plan_id)

    live_cell_source = notebook_analysis.get_by_notebook("nb-1").cells[1].source
    assert diff.changes[0]["original_source"] == live_cell_source == "def add(a, b):\n    return a + b"


def test_incomplete_diff_is_rejected_when_a_target_cell_no_longer_exists():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
            make_response(SMALLER_ANALYSIS_RESPONSE),
        ]
    )
    plan = _validated_plan(notebook_analysis, transformation, validation, NOTEBOOK, REQUEST)

    notebook_analysis.analyze(SMALLER_NOTEBOOK)

    with pytest.raises(UnmappedChangeError):
        diff_service.generate(plan.plan_id)


def test_plan_must_pass_validation_before_a_diff_can_be_generated():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(TRANSFORMATION_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST)

    with pytest.raises(UnvalidatedPlanError):
        diff_service.generate(plan.plan_id)


def test_plan_with_blocking_findings_cannot_be_diffed():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(BLOCKING_FINDINGS_RESPONSE),
        ]
    )
    notebook_analysis.analyze(NOTEBOOK)
    plan = transformation.plan("nb-1", REQUEST)
    validation.validate(plan.plan_id)

    with pytest.raises(PlanNotValidError):
        diff_service.generate(plan.plan_id)


def test_validate_detects_a_diff_gone_stale_after_the_cell_changed():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
            make_response(CHANGED_SOURCE_ANALYSIS_RESPONSE),
        ]
    )
    plan = _validated_plan(notebook_analysis, transformation, validation, NOTEBOOK, REQUEST)
    diff = diff_service.generate(plan.plan_id)

    assert diff_service.validate(diff.diff_id) is True

    notebook_analysis.analyze(CHANGED_SOURCE_NOTEBOOK)

    with pytest.raises(StaleDiffError):
        diff_service.validate(diff.diff_id)


def test_diff_output_is_deterministic_across_repeated_generation():
    notebook_analysis, transformation, validation, diff_service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
        ]
    )
    plan = _validated_plan(notebook_analysis, transformation, validation, NOTEBOOK, REQUEST)

    first = diff_service.generate(plan.plan_id)
    second = diff_service.generate(plan.plan_id)

    assert first.diff_id != second.diff_id
    assert first.changes == second.changes
    assert first.additions == second.additions
    assert first.deletions == second.deletions
