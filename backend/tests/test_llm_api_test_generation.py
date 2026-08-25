import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_schema_review import LLMAPISchemaReviewService
from backend.api_test_generation import (
    LLMAPITestGenerationService,
    SchemaNotApprovedError,
    UnknownTestError,
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
from backend.test_generation import EDGE, INVALID, VALID, LLMTestGenerationService, MalformedTestError, UnknownTestFieldError


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
    test_generation_service = LLMTestGenerationService(
        api_candidate_service, input_schema_service, output_schema_service, orchestration_service, context_service
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
    api_test_service = LLMAPITestGenerationService(
        exposure_service, schema_review_service, api_candidate_service, test_generation_service
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "test_generation": test_generation_service,
        "exposure": exposure_service,
        "review": schema_review_service,
        "api_tests": api_test_service,
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
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "add",
                "inputs": ["a", "b"],
                "outputs": ["sum"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            },
            {
                "function_name": "sub",
                "inputs": ["a", "b"],
                "outputs": ["diff"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            },
        ]
    }
)
ADD_INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            {"name": "a", "type": "int", "constraints": {}, "ambiguous": False},
            {"name": "b", "type": "int", "constraints": {}, "ambiguous": False},
        ]
    }
)
SUB_INPUT_SCHEMA_RESPONSE = ADD_INPUT_SCHEMA_RESPONSE
ADD_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "sum", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
SUB_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "diff", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
ADD_EXPOSURE_RESPONSE = json.dumps(
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
SUB_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "sub",
                "endpoint_name": "/sub",
                "method": "POST",
                "rationale": "Pure arithmetic function.",
                "confidence": 0.85,
            }
        ]
    }
)
EMPTY_REVIEW_RESPONSE = json.dumps({"findings": [], "confidence": 0.9})

ADD_TEST_GENERATION_RESPONSE = json.dumps(
    {
        "tests": [
            {
                "scenario": "adds two positive numbers",
                "category": "VALID",
                "input": {"a": 1, "b": 2},
                "expected_output": {"sum": 3},
                "confidence": 0.9,
            },
            {
                "scenario": "missing required field b",
                "category": "INVALID",
                "input": {"a": 1},
                "expected_output": {"raises": True, "reason": "b is required"},
                "confidence": 0.8,
            },
            {
                "scenario": "zeros",
                "category": "EDGE",
                "input": {"a": 0, "b": 0},
                "expected_output": {"sum": 0},
                "confidence": 0.7,
            },
        ]
    }
)
SUB_TEST_GENERATION_RESPONSE = json.dumps(
    {
        "tests": [
            {
                "scenario": "subtracts two positive numbers",
                "category": "VALID",
                "input": {"a": 5, "b": 2},
                "expected_output": {"diff": 3},
                "confidence": 0.9,
            },
            {
                "scenario": "missing required field b",
                "category": "INVALID",
                "input": {"a": 5},
                "expected_output": {"raises": True, "reason": "b is required"},
                "confidence": 0.8,
            },
            {
                "scenario": "zeros",
                "category": "EDGE",
                "input": {"a": 0, "b": 0},
                "expected_output": {"diff": 0},
                "confidence": 0.7,
            },
        ]
    }
)
UNKNOWN_FIELD_TEST_GENERATION_RESPONSE = json.dumps(
    {
        "tests": [
            {
                "scenario": "adds with an extra field",
                "category": "VALID",
                "input": {"a": 1, "b": 2, "c": 5},
                "expected_output": {"sum": 3},
                "confidence": 0.9,
            },
            {
                "scenario": "missing required field b",
                "category": "INVALID",
                "input": {"a": 1},
                "expected_output": {"raises": True, "reason": "b is required"},
                "confidence": 0.8,
            },
            {
                "scenario": "zeros",
                "category": "EDGE",
                "input": {"a": 0, "b": 0},
                "expected_output": {"sum": 0},
                "confidence": 0.7,
            },
        ]
    }
)


def _confident_intent(function_name):
    return LLMNotebookAPIIntent(
        notebook_id="nb-1",
        operations=[{"operation": f"expose {function_name}", "function": function_name, "ambiguous": False}],
        candidate_functions=[function_name],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.8,
    )


def _register_candidates(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    add_candidate, sub_candidate = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(add_candidate.candidate_id)
    env["output_schema"].infer(add_candidate.candidate_id)
    env["input_schema"].infer(sub_candidate.candidate_id)
    env["output_schema"].infer(sub_candidate.candidate_id)
    return add_candidate, sub_candidate


def _approved_add_recommendation(env):
    [recommendation] = env["exposure"].recommend(_confident_intent("add"))
    env["review"].review(recommendation)
    return recommendation


def test_generation_produces_valid_invalid_and_edge_cases_for_the_endpoint():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(ADD_INPUT_SCHEMA_RESPONSE),
            make_response(ADD_OUTPUT_SCHEMA_RESPONSE),
            make_response(SUB_INPUT_SCHEMA_RESPONSE),
            make_response(SUB_OUTPUT_SCHEMA_RESPONSE),
            make_response(ADD_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(ADD_TEST_GENERATION_RESPONSE),
        ]
    )
    _register_candidates(env)
    recommendation = _approved_add_recommendation(env)

    test_cases = env["api_tests"].generate(recommendation)

    by_category = {tc.category: tc for tc in test_cases}
    assert set(by_category) == {VALID, INVALID, EDGE}
    assert by_category[VALID].endpoint == "POST /add"
    assert by_category[VALID].request == {"a": 1, "b": 2}
    assert by_category[VALID].expected_response == {"sum": 3}
    assert by_category[INVALID].expected_response == {"raises": True, "reason": "b is required"}
    assert by_category[EDGE].request == {"a": 0, "b": 0}
    assert env["api_tests"].tests("POST /add") == test_cases


def test_schema_mismatch_is_rejected_by_the_underlying_generator():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(ADD_INPUT_SCHEMA_RESPONSE),
            make_response(ADD_OUTPUT_SCHEMA_RESPONSE),
            make_response(SUB_INPUT_SCHEMA_RESPONSE),
            make_response(SUB_OUTPUT_SCHEMA_RESPONSE),
            make_response(ADD_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(UNKNOWN_FIELD_TEST_GENERATION_RESPONSE),
        ]
    )
    _register_candidates(env)
    recommendation = _approved_add_recommendation(env)

    with pytest.raises(UnknownTestFieldError):
        env["api_tests"].generate(recommendation)


def test_malformed_llm_response_propagates():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(ADD_INPUT_SCHEMA_RESPONSE),
            make_response(ADD_OUTPUT_SCHEMA_RESPONSE),
            make_response(SUB_INPUT_SCHEMA_RESPONSE),
            make_response(SUB_OUTPUT_SCHEMA_RESPONSE),
            make_response(ADD_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response("not json"),
        ]
    )
    _register_candidates(env)
    recommendation = _approved_add_recommendation(env)

    with pytest.raises(MalformedTestError):
        env["api_tests"].generate(recommendation)


def test_generation_requires_an_approved_schema_review():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(ADD_INPUT_SCHEMA_RESPONSE),
            make_response(ADD_OUTPUT_SCHEMA_RESPONSE),
            make_response(SUB_INPUT_SCHEMA_RESPONSE),
            make_response(SUB_OUTPUT_SCHEMA_RESPONSE),
            make_response(ADD_EXPOSURE_RESPONSE),
        ]
    )
    _register_candidates(env)
    [recommendation] = env["exposure"].recommend(_confident_intent("add"))
    # Deliberately never schema-reviewed.

    with pytest.raises(SchemaNotApprovedError):
        env["api_tests"].generate(recommendation)


def test_validate_delegates_to_the_underlying_test_generation_service():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(ADD_INPUT_SCHEMA_RESPONSE),
            make_response(ADD_OUTPUT_SCHEMA_RESPONSE),
            make_response(SUB_INPUT_SCHEMA_RESPONSE),
            make_response(SUB_OUTPUT_SCHEMA_RESPONSE),
            make_response(ADD_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(ADD_TEST_GENERATION_RESPONSE),
        ]
    )
    _register_candidates(env)
    recommendation = _approved_add_recommendation(env)
    [test_case] = [tc for tc in env["api_tests"].generate(recommendation) if tc.category == VALID]

    assert env["api_tests"].validate(test_case.test_id) is True

    with pytest.raises(UnknownTestError):
        env["api_tests"].validate("never-generated")


def test_endpoint_isolation_keeps_test_cases_scoped_to_their_own_endpoint():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(ADD_INPUT_SCHEMA_RESPONSE),
            make_response(ADD_OUTPUT_SCHEMA_RESPONSE),
            make_response(SUB_INPUT_SCHEMA_RESPONSE),
            make_response(SUB_OUTPUT_SCHEMA_RESPONSE),
            make_response(ADD_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(ADD_TEST_GENERATION_RESPONSE),
            make_response(SUB_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(SUB_TEST_GENERATION_RESPONSE),
        ]
    )
    _register_candidates(env)
    add_recommendation = _approved_add_recommendation(env)
    add_tests = env["api_tests"].generate(add_recommendation)

    [sub_recommendation] = env["exposure"].recommend(_confident_intent("sub"))
    env["review"].review(sub_recommendation)
    sub_tests = env["api_tests"].generate(sub_recommendation)

    assert env["api_tests"].tests("POST /add") == add_tests
    assert env["api_tests"].tests("POST /sub") == sub_tests
    assert {tc.test_id for tc in add_tests}.isdisjoint({tc.test_id for tc in sub_tests})
    assert all(tc.endpoint == "POST /add" for tc in add_tests)
    assert all(tc.endpoint == "POST /sub" for tc in sub_tests)
