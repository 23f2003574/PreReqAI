import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_documentation import (
    DuplicateDocumentationError,
    ExampleSchemaMismatchError,
    LLMAPIDocumentationService,
    UnknownDocumentationError,
    UnsupportedClaimError,
)
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
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
    doc_service = LLMAPIDocumentationService(
        candidate_service,
        notebook_analysis_service,
        input_schema_service,
        output_schema_service,
        orchestration_service,
        context_service,
    )

    return notebook_analysis_service, candidate_service, input_schema_service, output_schema_service, doc_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [{"cell_type": "code", "source": "def add(a: int, b: int) -> int:\n    return a + b"}],
}
FUNCTIONS = [{"name": "add", "cell_index": 0}]
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
            }
        ]
    }
)


def input_field_entry(name, field_type="float"):
    return {"name": name, "type": field_type, "constraints": {}, "ambiguous": False}


INPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [input_field_entry("a"), input_field_entry("b")]}
)


def output_field_entry(name, field_type="str"):
    return {"name": name, "type": field_type, "nullable": False, "structure": {}, "contradictory": False}


OUTPUT_SCHEMA_RESPONSE = json.dumps({"fields": [output_field_entry("result")]})

VALID_DOC_RESPONSE = json.dumps(
    {
        "summary": "Add two integers.",
        "description": "Adds two integers a and b together and returns the sum.",
        "examples": [{"input": {"a": 1, "b": 2}, "output": {"result": 3}}],
    }
)


def build_doc_service(doc_response):
    """Runs the full analysis -> candidate -> input/output schema pipeline, then
    returns a doc_service ready to generate()/update() documentation from it."""
    (
        notebook_analysis_service,
        candidate_service,
        input_schema_service,
        output_schema_service,
        doc_service,
    ) = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(doc_response),
        ]
    )
    analysis = notebook_analysis_service.analyze(NOTEBOOK)
    candidates = candidate_service.analyze(analysis.analysis_id)
    input_schema_service.infer(candidates[0].candidate_id)
    output_schema_service.infer(candidates[0].candidate_id)
    return doc_service, candidates[0].candidate_id


def test_documentation_generation():
    doc_service, candidate_id = build_doc_service(VALID_DOC_RESPONSE)

    doc = doc_service.generate(candidate_id)

    assert doc.candidate_id == candidate_id
    assert doc.summary.strip() != ""
    assert doc.description.strip() != ""
    assert len(doc.examples) == 1
    assert doc.generated_at is not None


def test_schema_inclusion():
    doc_service, candidate_id = build_doc_service(VALID_DOC_RESPONSE)

    doc = doc_service.generate(candidate_id)

    assert doc.parameters == {
        "a": {"type": "int", "required": True},
        "b": {"type": "int", "required": True},
    }
    assert doc.response == {"result": {"type": "int", "nullable": False}}


def test_example_validation_rejects_mismatched_types():
    bad_response = json.dumps(
        {
            "summary": "Add two integers.",
            "description": "Adds a and b.",
            "examples": [{"input": {"a": 1, "b": "two"}, "output": {"result": 3}}],
        }
    )
    doc_service, candidate_id = build_doc_service(bad_response)

    with pytest.raises(ExampleSchemaMismatchError):
        doc_service.generate(candidate_id)


def test_example_validation_rejects_missing_required_field():
    bad_response = json.dumps(
        {
            "summary": "Add two integers.",
            "description": "Adds a and b.",
            "examples": [{"input": {"a": 1}, "output": {"result": 3}}],
        }
    )
    doc_service, candidate_id = build_doc_service(bad_response)

    with pytest.raises(ExampleSchemaMismatchError):
        doc_service.generate(candidate_id)


def test_unsupported_claim_rejection():
    bad_response = json.dumps(
        {
            "summary": "Add two integers.",
            "description": "Adds a and b.",
            "examples": [{"input": {"a": 1, "b": 2, "c": 99}, "output": {"result": 3}}],
        }
    )
    doc_service, candidate_id = build_doc_service(bad_response)

    with pytest.raises(UnsupportedClaimError):
        doc_service.generate(candidate_id)


UPDATED_DOC_RESPONSE = json.dumps(
    {
        "summary": "Add two integers together.",
        "description": "Returns a + b.",
        "examples": [
            {"input": {"a": 1, "b": 2}, "output": {"result": 3}},
            {"input": {"a": 5, "b": 5}, "output": {"result": 10}},
        ],
    }
)


def test_versioning():
    (
        notebook_analysis_service,
        candidate_service,
        input_schema_service,
        output_schema_service,
        doc_service,
    ) = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(VALID_DOC_RESPONSE),
            make_response(UPDATED_DOC_RESPONSE),
        ]
    )
    analysis = notebook_analysis_service.analyze(NOTEBOOK)
    candidates = candidate_service.analyze(analysis.analysis_id)
    candidate_id = candidates[0].candidate_id
    input_schema_service.infer(candidate_id)
    output_schema_service.infer(candidate_id)

    with pytest.raises(UnknownDocumentationError):
        doc_service.update(candidate_id)

    v1 = doc_service.generate(candidate_id)

    with pytest.raises(DuplicateDocumentationError):
        doc_service.generate(candidate_id)

    v2 = doc_service.update(candidate_id)

    assert v1 is not v2
    assert len(v1.examples) == 1
    assert len(v2.examples) == 2
    assert doc_service.get(candidate_id) is v2
    assert doc_service.history(candidate_id) == [v1, v2]
    assert doc_service.validate(candidate_id) is True


def test_deterministic_output():
    doc_service, candidate_id = build_doc_service(VALID_DOC_RESPONSE)
    doc_service.generate(candidate_id)

    first = doc_service.get(candidate_id)
    second = doc_service.get(candidate_id)

    assert first is second
    assert first.parameters == {
        "a": {"type": "int", "required": True},
        "b": {"type": "int", "required": True},
    }
    assert first.response == {"result": {"type": "int", "nullable": False}}
