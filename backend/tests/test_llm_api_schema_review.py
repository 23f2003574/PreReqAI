import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_schema_review import (
    APPROVED,
    REJECTED,
    LLMAPISchemaReviewService,
    MissingCandidateError,
    MissingSchemaError,
)
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_api_intent import LLMNotebookAPIIntent
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
    api_candidate_service = LLMAPICandidateService(
        notebook_analysis_service, orchestration_service=orchestration_service, context_service=context_service
    )
    input_schema_service = LLMInputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    output_schema_service = LLMOutputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    exposure_service = LLMAPIExposureService(notebook_analysis_service, orchestration_service, context_service)
    schema_review_service = LLMAPISchemaReviewService(
        exposure_service,
        api_candidate_service,
        input_schema_service,
        output_schema_service,
        orchestration_service,
        context_service,
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "exposure": exposure_service,
        "review": schema_review_service,
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
EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "add",
                "endpoint_name": "/add",
                "method": "POST",
                "rationale": "Pure arithmetic function.",
                "confidence": 0.85,
            }
        ]
    }
)
EMPTY_REVIEW_RESPONSE = json.dumps({"findings": [], "confidence": 0.9})
AMBIGUOUS_TYPE_REVIEW_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "category": "AMBIGUOUS_TYPE",
                "target": "a",
                "message": "field 'a' is typed int but used ambiguously across call sites.",
                "blocking": True,
            }
        ],
        "confidence": 0.5,
    }
)

DATA_NOTEBOOK = {
    "notebook_id": "nb-2",
    "cells": [{"cell_type": "code", "source": "def get_data(source) -> dict:\n    return fetch(source)"}],
}
DATA_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "get_data", "cell_index": 0}], "dependencies": []}
)
DATA_CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "get_data",
                "inputs": ["source"],
                "outputs": ["data"],
                "confidence": 0.9,
                "rationale": "Fetches structured data.",
            }
        ]
    }
)
DATA_INPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "source", "type": "str", "constraints": {}, "ambiguous": False}]}
)
DATA_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "data", "type": "dict", "nullable": False, "structure": {}, "contradictory": False}]}
)
DATA_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "get_data",
                "endpoint_name": "/data",
                "method": "GET",
                "rationale": "Read-only fetch.",
                "confidence": 0.7,
            }
        ]
    }
)


def _confident_intent(notebook_id, function_name):
    return LLMNotebookAPIIntent(
        notebook_id=notebook_id,
        operations=[{"operation": f"expose {function_name}", "function": function_name, "ambiguous": False}],
        candidate_functions=[function_name],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.8,
    )


def _register_add_candidate_with_schemas(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    return candidate


def test_valid_schema_is_approved():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
        ]
    )
    _register_add_candidate_with_schemas(env)
    [recommendation] = env["exposure"].recommend(_confident_intent("nb-1", "add"))

    review = env["review"].review(recommendation)

    assert review.function_name == "add"
    assert review.findings == []
    assert review.status == APPROVED
    assert review.confidence == 0.9
    assert env["review"].approved(review.review_id) is True


def test_ambiguous_type_finding_rejects_the_review():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(AMBIGUOUS_TYPE_REVIEW_RESPONSE),
        ]
    )
    _register_add_candidate_with_schemas(env)
    [recommendation] = env["exposure"].recommend(_confident_intent("nb-1", "add"))

    review = env["review"].review(recommendation)

    assert review.status == REJECTED
    assert env["review"].approved(review.review_id) is False
    assert env["review"].findings(review.review_id)[0]["category"] == "AMBIGUOUS_TYPE"


def test_missing_schema_is_rejected_before_any_llm_review_call():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(CANDIDATE_RESPONSE), make_response(EXPOSURE_RESPONSE)]
    )
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    env["api_candidate"].analyze(analysis.analysis_id)
    # Deliberately never inferred input/output schemas for this candidate.
    [recommendation] = env["exposure"].recommend(_confident_intent("nb-1", "add"))

    with pytest.raises(MissingSchemaError):
        env["review"].review(recommendation)


def test_unsupported_output_structure_is_flagged_deterministically():
    env = build_env(
        [
            make_response(DATA_ANALYSIS_RESPONSE),
            make_response(DATA_CANDIDATE_RESPONSE),
            make_response(DATA_INPUT_SCHEMA_RESPONSE),
            make_response(DATA_OUTPUT_SCHEMA_RESPONSE),
            make_response(DATA_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
        ]
    )
    analysis = env["notebook_analysis"].analyze(DATA_NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    [recommendation] = env["exposure"].recommend(_confident_intent("nb-2", "get_data"))

    review = env["review"].review(recommendation)

    assert review.status == REJECTED
    categories = {f["category"] for f in review.findings}
    assert "UNSUPPORTED_STRUCTURE" in categories


def test_findings_accessor_reflects_the_recorded_findings():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(AMBIGUOUS_TYPE_REVIEW_RESPONSE),
        ]
    )
    _register_add_candidate_with_schemas(env)
    [recommendation] = env["exposure"].recommend(_confident_intent("nb-1", "add"))

    review = env["review"].review(recommendation)

    assert env["review"].findings(review.review_id) == review.findings
    assert any(f["blocking"] for f in env["review"].findings(review.review_id))


def test_approved_and_rejected_states_are_distinguishable():
    approved_env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
        ]
    )
    _register_add_candidate_with_schemas(approved_env)
    [approved_rec] = approved_env["exposure"].recommend(_confident_intent("nb-1", "add"))
    approved_review = approved_env["review"].review(approved_rec)

    rejected_env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(AMBIGUOUS_TYPE_REVIEW_RESPONSE),
        ]
    )
    _register_add_candidate_with_schemas(rejected_env)
    [rejected_rec] = rejected_env["exposure"].recommend(_confident_intent("nb-1", "add"))
    rejected_review = rejected_env["review"].review(rejected_rec)

    assert approved_env["review"].approved(approved_review.review_id) is True
    assert rejected_env["review"].approved(rejected_review.review_id) is False


def test_review_requires_a_registered_candidate():
    env = build_env([make_response(ANALYSIS_RESPONSE), make_response(EXPOSURE_RESPONSE)])
    env["notebook_analysis"].analyze(NOTEBOOK)
    # "add" exists in the notebook's own analysis but was never registered as an API candidate.
    [recommendation] = env["exposure"].recommend(_confident_intent("nb-1", "add"))

    with pytest.raises(MissingCandidateError):
        env["review"].review(recommendation)


PROCESS_NOTEBOOK = {
    "notebook_id": "nb-3",
    "cells": [{"cell_type": "code", "source": "def process(payload):\n    return {'result': payload}"}],
}
PROCESS_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "process", "cell_index": 0}], "dependencies": []}
)
PROCESS_CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "process",
                "inputs": ["payload"],
                "outputs": ["result"],
                "confidence": 0.9,
                "rationale": "Processes a structured payload.",
            }
        ]
    }
)
PROCESS_INPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "payload", "type": "dict", "constraints": {}, "ambiguous": False}]}
)
PROCESS_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "result", "type": "dict", "nullable": False, "structure": {"keys": []}, "contradictory": False}]}
)
PROCESS_GET_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "process",
                "endpoint_name": "/process",
                "method": "GET",
                "rationale": "Read-only lookup.",
                "confidence": 0.6,
            }
        ]
    }
)


def test_get_endpoint_with_structured_required_input_uses_the_real_schema_data():
    env = build_env(
        [
            make_response(PROCESS_ANALYSIS_RESPONSE),
            make_response(PROCESS_CANDIDATE_RESPONSE),
            make_response(PROCESS_INPUT_SCHEMA_RESPONSE),
            make_response(PROCESS_OUTPUT_SCHEMA_RESPONSE),
            make_response(PROCESS_GET_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
        ]
    )
    analysis = env["notebook_analysis"].analyze(PROCESS_NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    [recommendation] = env["exposure"].recommend(_confident_intent("nb-3", "process"))

    review = env["review"].review(recommendation)

    assert review.status == REJECTED
    categories = {f["category"] for f in review.findings}
    assert "SCHEMA_CONFLICT" in categories
