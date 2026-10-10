import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.output_schema import LLMOutputSchemaService
from backend.test_generation import (
    LLMTestGenerationService,
    MalformedTestError,
    UnknownTestFieldError,
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
    test_service = LLMTestGenerationService(
        candidate_service, input_schema_service, output_schema_service, orchestration_service, context_service
    )

    return (
        notebook_analysis_service,
        candidate_service,
        input_schema_service,
        output_schema_service,
        test_service,
    )


def notebook_for(notebook_id, function_name="add", source="def add(a: int, b: int) -> int:\n    return a + b"):
    return {"notebook_id": notebook_id, "cells": [{"cell_type": "code", "source": source}]}


def analysis_response(function_name):
    return json.dumps(
        {"imports": [], "functions": [{"name": function_name, "cell_index": 0}], "dependencies": []}
    )


def candidate_response(function_name, inputs, outputs):
    return json.dumps(
        {
            "candidates": [
                {
                    "function_name": function_name,
                    "inputs": inputs,
                    "outputs": outputs,
                    "confidence": 0.9,
                    "rationale": "Simple pure function.",
                }
            ]
        }
    )


def input_field_entry(name, field_type="float"):
    return {"name": name, "type": field_type, "constraints": {}, "ambiguous": False}


def output_field_entry(name, field_type="str"):
    return {"name": name, "type": field_type, "nullable": False, "structure": {}, "contradictory": False}


INPUT_SCHEMA_RESPONSE = json.dumps({"fields": [input_field_entry("a"), input_field_entry("b")]})
OUTPUT_SCHEMA_RESPONSE = json.dumps({"fields": [output_field_entry("result")]})

VALID_TESTS_RESPONSE = json.dumps(
    {
        "tests": [
            {
                "scenario": "adds two positive integers",
                "category": "VALID",
                "input": {"a": 1, "b": 2},
                "expected_output": {"result": 3},
                "confidence": 0.9,
            },
            {
                "scenario": "adding zero to zero",
                "category": "EDGE",
                "input": {"a": 0, "b": 0},
                "expected_output": {"result": 0},
                "confidence": 0.8,
            },
            {
                "scenario": "missing required field b",
                "category": "INVALID",
                "input": {"a": 1},
                "expected_output": {"raises": True, "reason": "b is required"},
                "confidence": 0.85,
            },
        ]
    }
)


def _generate_with_response(tests_response):
    notebook = notebook_for("nb-1")
    (
        notebook_analysis_service,
        candidate_service,
        input_schema_service,
        output_schema_service,
        test_service,
    ) = build_env(
        [
            make_response(analysis_response("add")),
            make_response(candidate_response("add", ["a", "b"], ["result"])),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(tests_response),
        ]
    )
    analysis = notebook_analysis_service.analyze(notebook)
    candidates = candidate_service.analyze(analysis.analysis_id)
    candidate_id = candidates[0].candidate_id
    input_schema_service.infer(candidate_id)
    output_schema_service.infer(candidate_id)
    generated = test_service.generate(candidate_id)
    return test_service, candidate_id, generated


def test_valid_case_generation():
    test_service, candidate_id, generated = _generate_with_response(VALID_TESTS_RESPONSE)

    valid_tests = [t for t in generated if t.category == "VALID"]
    assert len(valid_tests) == 1
    assert valid_tests[0].input == {"a": 1, "b": 2}
    assert valid_tests[0].expected_output == {"result": 3}
    assert test_service.tests(candidate_id) == generated


def test_invalid_case_generation():
    _, _, generated = _generate_with_response(VALID_TESTS_RESPONSE)

    invalid_tests = [t for t in generated if t.category == "INVALID"]
    assert len(invalid_tests) == 1
    assert invalid_tests[0].expected_output["raises"] is True
    assert invalid_tests[0].expected_output["reason"].strip() != ""


def test_edge_case_generation():
    _, _, generated = _generate_with_response(VALID_TESTS_RESPONSE)

    edge_tests = [t for t in generated if t.category == "EDGE"]
    assert len(edge_tests) == 1
    assert edge_tests[0].input == {"a": 0, "b": 0}


def test_schema_mismatch_rejection():
    bad_response = json.dumps(
        {
            "tests": [
                {
                    "scenario": "unknown field",
                    "category": "VALID",
                    "input": {"a": 1, "b": 2, "c": 99},
                    "expected_output": {"result": 3},
                    "confidence": 0.9,
                },
                {
                    "scenario": "edge",
                    "category": "EDGE",
                    "input": {"a": 0, "b": 0},
                    "expected_output": {"result": 0},
                    "confidence": 0.8,
                },
                {
                    "scenario": "invalid",
                    "category": "INVALID",
                    "input": {"a": 1},
                    "expected_output": {"raises": True, "reason": "b is required"},
                    "confidence": 0.85,
                },
            ]
        }
    )

    with pytest.raises(UnknownTestFieldError):
        _generate_with_response(bad_response)


@pytest.mark.parametrize(
    "bad_response",
    [
        json.dumps(
            {
                "tests": [
                    {
                        "scenario": "bad category",
                        "category": "BOUNDARY",
                        "input": {"a": 1, "b": 2},
                        "expected_output": {"result": 3},
                        "confidence": 0.9,
                    }
                ]
            }
        ),
        json.dumps(
            {
                "tests": [
                    {
                        "scenario": "only valid",
                        "category": "VALID",
                        "input": {"a": 1, "b": 2},
                        "expected_output": {"result": 3},
                        "confidence": 0.9,
                    }
                ]
            }
        ),
    ],
)
def test_category_validation(bad_response):
    with pytest.raises(MalformedTestError):
        _generate_with_response(bad_response)


def test_candidate_isolation():
    (
        notebook_analysis_service,
        candidate_service,
        input_schema_service,
        output_schema_service,
        test_service,
    ) = build_env(
        [
            make_response(analysis_response("add")),
            make_response(candidate_response("add", ["a", "b"], ["result"])),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(VALID_TESTS_RESPONSE),
            make_response(analysis_response("multiply")),
            make_response(candidate_response("multiply", ["a", "b"], ["result"])),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(VALID_TESTS_RESPONSE),
        ]
    )

    analysis_1 = notebook_analysis_service.analyze(
        notebook_for("nb-1", "add", "def add(a: int, b: int) -> int:\n    return a + b")
    )
    candidate_1 = candidate_service.analyze(analysis_1.analysis_id)[0]
    input_schema_service.infer(candidate_1.candidate_id)
    output_schema_service.infer(candidate_1.candidate_id)
    generated_1 = test_service.generate(candidate_1.candidate_id)

    analysis_2 = notebook_analysis_service.analyze(
        notebook_for("nb-2", "multiply", "def multiply(a: int, b: int) -> int:\n    return a * b")
    )
    candidate_2 = candidate_service.analyze(analysis_2.analysis_id)[0]
    input_schema_service.infer(candidate_2.candidate_id)
    output_schema_service.infer(candidate_2.candidate_id)
    generated_2 = test_service.generate(candidate_2.candidate_id)

    assert test_service.tests(candidate_1.candidate_id) == generated_1
    assert test_service.tests(candidate_2.candidate_id) == generated_2
    assert set(t.test_id for t in generated_1).isdisjoint(t.test_id for t in generated_2)

    for test in generated_1:
        assert test_service.validate(test.test_id) is True
