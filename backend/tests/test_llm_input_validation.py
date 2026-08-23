import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.input_schema import LLMInputSchemaService
from backend.input_validation import LLMInputValidationService, ValidationFailedError
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
    candidate_service = LLMAPICandidateService(
        notebook_analysis_service,
        orchestration_service=orchestration_service,
        context_service=context_service,
    )
    input_schema_service = LLMInputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    validation_service = LLMInputValidationService(orchestration_service, context_service)

    return notebook_analysis_service, candidate_service, input_schema_service, validation_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {
            "cell_type": "code",
            "source": "def create_user(name: str, age, active=True):\n    return name",
        }
    ],
}
FUNCTIONS = [{"name": "create_user", "cell_index": 0}]
ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": FUNCTIONS, "dependencies": []})
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "create_user",
                "inputs": ["name", "age", "active"],
                "outputs": ["result"],
                "confidence": 0.9,
                "rationale": "Simple constructor-style function.",
            }
        ]
    }
)


def field_entry(name, field_type, constraints=None):
    return {"name": name, "type": field_type, "constraints": constraints or {}, "ambiguous": False}


INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            field_entry("name", "float"),  # explicit annotation ("str") must win over this
            field_entry("age", "int", constraints={"min": 0}),
            field_entry("active", "bool"),
        ]
    }
)


def build_schema():
    notebook_analysis_service, candidate_service, input_schema_service, _ = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
        ]
    )
    analysis = notebook_analysis_service.analyze(NOTEBOOK)
    candidates = candidate_service.analyze(analysis.analysis_id)
    return input_schema_service.infer(candidates[0].candidate_id)


def _default_messages_response(schema) -> str:
    keys = []
    for field in schema.fields:
        if field in schema.required:
            keys.append(f"{field}:required")
        keys.append(f"{field}:type")
        if field in schema.defaults:
            keys.append(f"{field}:default")
        for constraint_key in schema.constraints.get(field, {}):
            keys.append(f"{field}:{constraint_key}")
    return json.dumps({"messages": {key: f"invalid {key}" for key in keys}})


def build_validation_env(schema, messages_response=None):
    """A fresh orchestration/context pair dedicated to LLMInputValidationService,
    reused via infer() -- separate from the pipeline that produced the schema."""
    if messages_response is None:
        messages_response = _default_messages_response(schema)

    _, _, _, validation_service = build_env([make_response(messages_response)])
    rules = validation_service.infer(schema)
    return validation_service, rules


def test_required_field_validation():
    schema = build_schema()
    validation_service, _ = build_validation_env(schema)

    violations = validation_service.violations(schema.candidate_id, {"age": 30, "active": True})

    assert any(v.field == "name" and v.rule == "required" for v in violations)


def test_type_mismatch():
    schema = build_schema()
    validation_service, _ = build_validation_env(schema)

    violations = validation_service.violations(
        schema.candidate_id, {"name": "Alice", "age": "not-a-number", "active": True}
    )

    assert any(v.field == "age" and v.rule == "type" for v in violations)


def test_constraint_violation():
    schema = build_schema()
    validation_service, _ = build_validation_env(schema)

    violations = validation_service.violations(
        schema.candidate_id, {"name": "Alice", "age": -5, "active": True}
    )

    assert any(v.field == "age" and v.rule == "min" for v in violations)


def test_defaults_do_not_force_a_violation_when_omitted():
    schema = build_schema()
    validation_service, rules = build_validation_env(schema)

    assert any(r.field == "active" and r.rule == "default" and r.value is True for r in rules)

    violations = validation_service.violations(schema.candidate_id, {"name": "Alice", "age": 30})

    assert not any(v.field == "active" for v in violations)


def test_multiple_violations_are_all_reported():
    schema = build_schema()
    validation_service, _ = build_validation_env(schema)

    violations = validation_service.violations(
        schema.candidate_id, {"age": -5, "active": "not-a-bool"}
    )

    fields = {(v.field, v.rule) for v in violations}
    assert ("name", "required") in fields
    assert ("age", "min") in fields
    assert ("active", "type") in fields
    assert len(violations) == 3

    with pytest.raises(ValidationFailedError) as excinfo:
        validation_service.validate(schema.candidate_id, {"age": -5, "active": "not-a-bool"})
    assert len(excinfo.value.violations) == 3


def test_valid_payload_has_no_violations():
    schema = build_schema()
    validation_service, _ = build_validation_env(schema)

    payload = {"name": "Alice", "age": 30, "active": False}

    assert validation_service.violations(schema.candidate_id, payload) == []
    assert validation_service.validate(schema.candidate_id, payload) is True
