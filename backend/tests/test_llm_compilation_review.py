import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.compilation_plan import LLMCompilationPlanningService
from backend.compilation_review import LLMCompilationReviewService, UnknownReviewError
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
    review_service = LLMCompilationReviewService(plan_service, orchestration_service, context_service)

    return {
        "notebook_analysis": notebook_analysis_service,
        "candidate": candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "dependency": dependency_service,
        "plan": plan_service,
        "review": review_service,
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

NON_CONFLICTING_ENDPOINTS_RESPONSE = json.dumps(
    {
        "endpoints": [
            {"candidate_id": CANDIDATE_ID_1, "method": "POST", "path": "/add"},
            {"candidate_id": CANDIDATE_ID_2, "method": "POST", "path": "/multiply"},
        ]
    }
)
CONFLICTING_ENDPOINTS_RESPONSE = json.dumps(
    {
        "endpoints": [
            {"candidate_id": CANDIDATE_ID_1, "method": "POST", "path": "/compute"},
            {"candidate_id": CANDIDATE_ID_2, "method": "POST", "path": "/compute"},
        ]
    }
)
GET_ENDPOINTS_RESPONSE = json.dumps(
    {
        "endpoints": [
            {"candidate_id": CANDIDATE_ID_1, "method": "GET", "path": "/add"},
            {"candidate_id": CANDIDATE_ID_2, "method": "POST", "path": "/multiply"},
        ]
    }
)

EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})


def build_plan(endpoints_response=NON_CONFLICTING_ENDPOINTS_RESPONSE, extra_script=()):
    script = [
        make_response(ANALYSIS_RESPONSE),
        make_response(CANDIDATE_RESPONSE),
        make_response(INPUT_SCHEMA_RESPONSE),
        make_response(OUTPUT_SCHEMA_RESPONSE),
        make_response(INPUT_SCHEMA_RESPONSE),
        make_response(OUTPUT_SCHEMA_RESPONSE),
        make_response(DEPENDENCY_RESPONSE),
        make_response(endpoints_response),
    ]
    script.extend(extra_script)

    services = build_env(script)
    analysis = services["notebook_analysis"].analyze(NOTEBOOK)
    candidates = services["candidate"].analyze(analysis.analysis_id)
    assert [c.candidate_id for c in candidates] == [CANDIDATE_ID_1, CANDIDATE_ID_2]

    services["input_schema"].infer(CANDIDATE_ID_1)
    services["output_schema"].infer(CANDIDATE_ID_1)
    services["input_schema"].infer(CANDIDATE_ID_2)
    services["output_schema"].infer(CANDIDATE_ID_2)
    services["dependency"].analyze(analysis.analysis_id)

    plan = services["plan"].build("nb-1")
    return services, plan


def test_successful_review():
    services, plan = build_plan(extra_script=[make_response(EMPTY_FINDINGS_RESPONSE)])

    review = services["review"].review(plan.plan_id)

    assert review.plan_id == plan.plan_id
    assert review.status == "APPROVED"
    assert review.findings == []
    assert services["review"].approved(plan.plan_id) is True
    assert services["review"].findings(plan.plan_id) == []


def test_conflicting_endpoints():
    services, plan = build_plan(
        endpoints_response=CONFLICTING_ENDPOINTS_RESPONSE,
        extra_script=[make_response(EMPTY_FINDINGS_RESPONSE)],
    )

    review = services["review"].review(plan.plan_id)

    assert review.status == "REJECTED"
    assert any(f["category"] == "CONFLICTING_ROUTE" and f["blocking"] for f in review.findings)


def test_unresolved_dependency():
    truncated_analysis_response = json.dumps(
        {"imports": [], "functions": [FUNCTIONS[0]], "dependencies": []}
    )
    services, plan = build_plan(
        extra_script=[make_response(truncated_analysis_response), make_response(EMPTY_FINDINGS_RESPONSE)]
    )

    truncated_notebook = {
        "notebook_id": "nb-1",
        "cells": [{"cell_type": "code", "source": "def add(a: int, b: int) -> int:\n    return a + b"}],
    }
    services["notebook_analysis"].analyze(truncated_notebook)

    review = services["review"].review(plan.plan_id)

    assert review.status == "REJECTED"
    assert any(f["category"] == "UNRESOLVED_DEPENDENCY" and f["blocking"] for f in review.findings)


def test_schema_conflict():
    services, plan = build_plan(
        endpoints_response=GET_ENDPOINTS_RESPONSE,
        extra_script=[make_response(EMPTY_FINDINGS_RESPONSE)],
    )
    # give candidate 1 a required "list" input, which conflicts with its GET endpoint
    input_schema = services["input_schema"].get(CANDIDATE_ID_1)
    input_schema.types["a"] = "list"

    review = services["review"].review(plan.plan_id)

    assert review.status == "REJECTED"
    assert any(f["category"] == "SCHEMA_CONFLICT" and f["blocking"] for f in review.findings)


def test_blocking_finding_from_llm():
    llm_findings_response = json.dumps(
        {
            "findings": [
                {
                    "category": "UNSAFE_DECISION",
                    "target": CANDIDATE_ID_1,
                    "message": "Endpoint exposes raw arithmetic with no rate limiting guidance.",
                    "blocking": True,
                }
            ]
        }
    )
    services, plan = build_plan(extra_script=[make_response(llm_findings_response)])

    review = services["review"].review(plan.plan_id)

    assert review.status == "REJECTED"
    assert any(f["category"] == "UNSAFE_DECISION" and f["blocking"] for f in review.findings)


def test_approved_rejected_state():
    services, plan = build_plan(extra_script=[make_response(EMPTY_FINDINGS_RESPONSE)])

    with pytest.raises(UnknownReviewError):
        services["review"].approved(plan.plan_id)
    with pytest.raises(UnknownReviewError):
        services["review"].findings(plan.plan_id)

    review = services["review"].review(plan.plan_id)
    assert review.status == "APPROVED"
    assert services["review"].approved(plan.plan_id) is True

    non_blocking_response = json.dumps(
        {
            "findings": [
                {
                    "category": "STYLE_SUGGESTION",
                    "target": CANDIDATE_ID_1,
                    "message": "Consider a more descriptive path than /add.",
                    "blocking": False,
                }
            ]
        }
    )
    services2, plan2 = build_plan(extra_script=[make_response(non_blocking_response)])
    review2 = services2["review"].review(plan2.plan_id)

    assert review2.status == "APPROVED"
    assert services2["review"].approved(plan2.plan_id) is True
    assert len(services2["review"].findings(plan2.plan_id)) == 1
