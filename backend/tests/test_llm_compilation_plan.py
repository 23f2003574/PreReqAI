import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.compilation_plan import (
    EndpointCandidateError,
    LLMCompilationPlanningService,
    MissingSchemaError,
    UnresolvableDependencyError,
)
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_dependencies import LLMNotebookDependencyService
from backend.output_schema import LLMOutputSchemaService


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
    candidate_service = LLMAPICandidateService(
        notebook_analysis_service,
        orchestration_service=orchestration_service,
        context_service=context_service,
    )
    input_schema_service = LLMInputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    output_schema_service = LLMOutputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    dependency_service = LLMNotebookDependencyService(
        notebook_analysis_service, orchestration_service, context_service
    )
    plan_service = LLMCompilationPlanningService(
        candidate_service,
        notebook_analysis_service,
        input_schema_service,
        output_schema_service,
        dependency_service,
        orchestration_service,
        context_service,
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "candidate": candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "dependency": dependency_service,
        "plan": plan_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "code", "source": "def add(a: int, b: int) -> int:\n    return a + b"},
        {"cell_type": "code", "source": "def multiply(a: int, b: int) -> int:\n    return a * b"},
    ],
}
FUNCTIONS = [{"name": "add", "cell_index": 0}, {"name": "multiply", "cell_index": 1}]
ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": FUNCTIONS, "dependencies": []})
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "add",
                "inputs": ["a", "b"],
                "outputs": ["result"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            },
            {
                "function_name": "multiply",
                "inputs": ["a", "b"],
                "outputs": ["result"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            },
        ]
    }
)


def input_field_entry(name, field_type="float"):
    return {"name": name, "type": field_type, "constraints": {}, "ambiguous": False}


INPUT_SCHEMA_RESPONSE = json.dumps({"fields": [input_field_entry("a"), input_field_entry("b")]})


def output_field_entry(name, field_type="str"):
    return {"name": name, "type": field_type, "nullable": False, "structure": {}, "contradictory": False}


OUTPUT_SCHEMA_RESPONSE = json.dumps({"fields": [output_field_entry("result")]})

DEPENDENCY_RESPONSE = json.dumps(
    {
        "edges": [
            {"source": "cell:0", "target": "function:add", "dependency_type": "FUNCTION", "confidence": 0.9},
            {"source": "cell:1", "target": "function:multiply", "dependency_type": "FUNCTION", "confidence": 0.9},
        ]
    }
)

CANDIDATE_ID_1 = "candidate-nb-1-1"
CANDIDATE_ID_2 = "candidate-nb-1-2"

ENDPOINTS_RESPONSE = json.dumps(
    {
        "endpoints": [
            {"candidate_id": CANDIDATE_ID_1, "method": "POST", "path": "/add"},
            {"candidate_id": CANDIDATE_ID_2, "method": "POST", "path": "/multiply"},
        ]
    }
)


def build_full_plan(endpoints_response=ENDPOINTS_RESPONSE, skip_second_output_schema=False, extra_script=()):
    script = [
        make_response(ANALYSIS_RESPONSE),
        make_response(CANDIDATE_RESPONSE),
        make_response(INPUT_SCHEMA_RESPONSE),
        make_response(OUTPUT_SCHEMA_RESPONSE),
        make_response(INPUT_SCHEMA_RESPONSE),
    ]
    if not skip_second_output_schema:
        script.append(make_response(OUTPUT_SCHEMA_RESPONSE))
    script.append(make_response(DEPENDENCY_RESPONSE))
    script.append(make_response(endpoints_response))
    script.extend(extra_script)

    services = build_env(script)
    analysis = services["notebook_analysis"].analyze(NOTEBOOK)
    candidates = services["candidate"].analyze(analysis.analysis_id)
    assert [c.candidate_id for c in candidates] == [CANDIDATE_ID_1, CANDIDATE_ID_2]

    services["input_schema"].infer(CANDIDATE_ID_1)
    services["output_schema"].infer(CANDIDATE_ID_1)
    services["input_schema"].infer(CANDIDATE_ID_2)
    if not skip_second_output_schema:
        services["output_schema"].infer(CANDIDATE_ID_2)

    services["dependency"].analyze(analysis.analysis_id)

    return services


def test_plan_construction():
    services = build_full_plan()

    plan = services["plan"].build("nb-1")

    assert plan.notebook_id == "nb-1"
    assert plan.plan_id.startswith("plan-nb-1-")
    assert len(plan.candidates) == 2
    assert plan.generated_at is not None


def test_candidate_schema_consistency():
    services = build_full_plan()

    plan = services["plan"].build("nb-1")

    assert set(plan.schemas.keys()) == {CANDIDATE_ID_1, CANDIDATE_ID_2}
    for candidate_id in (CANDIDATE_ID_1, CANDIDATE_ID_2):
        assert plan.validations[candidate_id]["has_input_schema"] is True
        assert plan.validations[candidate_id]["has_output_schema"] is True
        assert plan.validations[candidate_id]["has_endpoint"] is True
        assert plan.schemas[candidate_id]["input"].candidate_id == candidate_id
        assert plan.schemas[candidate_id]["output"].candidate_id == candidate_id


def test_dependency_validation_detects_staleness():
    truncated_analysis_response = json.dumps(
        {"imports": [], "functions": [FUNCTIONS[0]], "dependencies": []}
    )
    services = build_full_plan(extra_script=[make_response(truncated_analysis_response)])
    plan = services["plan"].build("nb-1")
    assert services["plan"].validate(plan.plan_id) is True

    truncated_notebook = {
        "notebook_id": "nb-1",
        "cells": [{"cell_type": "code", "source": "def add(a: int, b: int) -> int:\n    return a + b"}],
    }
    services["notebook_analysis"].analyze(truncated_notebook)

    with pytest.raises(UnresolvableDependencyError):
        services["plan"].validate(plan.plan_id)


def test_missing_schema_rejection():
    services = build_full_plan(skip_second_output_schema=True)

    with pytest.raises(MissingSchemaError):
        services["plan"].build("nb-1")


def test_endpoint_generation():
    services = build_full_plan()

    plan = services["plan"].build("nb-1")

    assert services["plan"].endpoints(plan.plan_id) == plan.endpoints
    endpoints_by_candidate = {e["candidate_id"]: e for e in plan.endpoints}
    assert endpoints_by_candidate[CANDIDATE_ID_1] == {
        "candidate_id": CANDIDATE_ID_1,
        "method": "POST",
        "path": "/add",
    }
    assert endpoints_by_candidate[CANDIDATE_ID_2]["path"] == "/multiply"


def test_endpoint_must_reference_valid_candidate():
    bad_endpoints = json.dumps(
        {
            "endpoints": [
                {"candidate_id": "candidate-does-not-exist", "method": "POST", "path": "/add"},
                {"candidate_id": CANDIDATE_ID_2, "method": "POST", "path": "/multiply"},
            ]
        }
    )
    services = build_full_plan(endpoints_response=bad_endpoints)

    with pytest.raises(EndpointCandidateError):
        services["plan"].build("nb-1")


def test_immutable_validated_plan():
    services = build_full_plan()

    plan = services["plan"].build("nb-1")

    assert isinstance(plan.candidates, tuple)
    assert isinstance(plan.dependencies, tuple)
    assert isinstance(plan.endpoints, tuple)

    with pytest.raises(AttributeError):
        plan.candidates.append("nope")
    with pytest.raises(TypeError):
        plan.schemas["new"] = {}
    with pytest.raises(TypeError):
        plan.validations["new"] = {}
    with pytest.raises(Exception):
        plan.notebook_id = "nb-2"

    assert services["plan"].validate(plan.plan_id) is True
    assert services["plan"].dependencies(plan.plan_id) == plan.dependencies
