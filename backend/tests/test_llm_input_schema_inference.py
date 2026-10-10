import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.input_schema import (
    AmbiguousInputSchemaError,
    InvalidSchemaError,
    LLMInputSchema,
    LLMInputSchemaService,
    MalformedSchemaResponseError,
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
    candidate_service = LLMAPICandidateService(
        notebook_analysis_service,
        orchestration_service=orchestration_service,
        context_service=context_service,
    )
    schema_service = LLMInputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )

    return notebook_analysis_service, candidate_service, schema_service


def run_pipeline(notebook, functions, candidate_inputs, schema_response):
    analysis_response = json.dumps({"imports": [], "functions": functions, "dependencies": []})
    candidate_response = json.dumps(
        {
            "candidates": [
                {
                    "function_name": functions[0]["name"],
                    "inputs": candidate_inputs,
                    "outputs": ["result"],
                    "confidence": 0.9,
                    "rationale": "Simple pure function.",
                }
            ]
        }
    )

    notebook_analysis_service, candidate_service, schema_service = build_env(
        [make_response(analysis_response), make_response(candidate_response), make_response(schema_response)]
    )
    analysis = notebook_analysis_service.analyze(notebook)
    candidates = candidate_service.analyze(analysis.analysis_id)
    schema = schema_service.infer(candidates[0].candidate_id)
    return schema_service, schema, candidates[0]


def field_entry(name, field_type, constraints=None, ambiguous=False):
    return {"name": name, "type": field_type, "constraints": constraints or {}, "ambiguous": ambiguous}


def test_primitive_types_are_preserved_from_annotations():
    notebook = {
        "notebook_id": "nb-1",
        "cells": [{"cell_type": "code", "source": "def add(a: int, b: int) -> int:\n    return a + b"}],
    }
    functions = [{"name": "add", "cell_index": 0}]
    schema_response = json.dumps(
        {
            "fields": [
                field_entry("a", "float", constraints={"min": 0}),
                field_entry("b", "float"),
            ]
        }
    )

    _, schema, _ = run_pipeline(notebook, functions, ["a", "b"], schema_response)

    assert schema.types == {"a": "int", "b": "int"}
    assert schema.required == ["a", "b"]
    assert schema.defaults == {}
    assert schema.constraints == {"a": {"min": 0}}


def test_optional_inputs_with_defaults():
    notebook = {
        "notebook_id": "nb-2",
        "cells": [{"cell_type": "code", "source": "def scale(x, factor=2.0):\n    return x * factor"}],
    }
    functions = [{"name": "scale", "cell_index": 0}]
    schema_response = json.dumps(
        {"fields": [field_entry("x", "float"), field_entry("factor", "float")]}
    )

    _, schema, _ = run_pipeline(notebook, functions, ["x", "factor"], schema_response)

    assert schema.required == ["x"]
    assert schema.defaults == {"factor": 2.0}
    assert schema.types == {"x": "float", "factor": "float"}


def test_required_fields_distinguished_from_optional():
    notebook = {
        "notebook_id": "nb-3",
        "cells": [{"cell_type": "code", "source": "def f(a, b=1, c=None):\n    return a"}],
    }
    functions = [{"name": "f", "cell_index": 0}]
    schema_response = json.dumps(
        {"fields": [field_entry("a", "int"), field_entry("b", "int"), field_entry("c", "str")]}
    )

    _, schema, _ = run_pipeline(notebook, functions, ["a", "b", "c"], schema_response)

    assert schema.required == ["a"]
    assert set(schema.defaults) == {"b", "c"}
    assert schema.defaults["b"] == 1
    assert schema.defaults["c"] is None


def test_constraints_are_captured_per_field():
    notebook = {
        "notebook_id": "nb-4",
        "cells": [{"cell_type": "code", "source": "def clamp(value):\n    return value"}],
    }
    functions = [{"name": "clamp", "cell_index": 0}]
    schema_response = json.dumps(
        {"fields": [field_entry("value", "int", constraints={"min": 0, "max": 100})]}
    )

    _, schema, _ = run_pipeline(notebook, functions, ["value"], schema_response)

    assert schema.constraints == {"value": {"min": 0, "max": 100}}


def test_ambiguous_inference_is_rejected():
    notebook = {
        "notebook_id": "nb-5",
        "cells": [{"cell_type": "code", "source": "def add(a, b):\n    return a + b"}],
    }
    functions = [{"name": "add", "cell_index": 0}]
    schema_response = json.dumps(
        {"fields": [field_entry("a", "int", ambiguous=True), field_entry("b", "int")]}
    )

    with pytest.raises(AmbiguousInputSchemaError):
        run_pipeline(notebook, functions, ["a", "b"], schema_response)


def test_unrecognized_inferred_type_is_rejected():
    notebook = {
        "notebook_id": "nb-6",
        "cells": [{"cell_type": "code", "source": "def add(a, b):\n    return a + b"}],
    }
    functions = [{"name": "add", "cell_index": 0}]
    schema_response = json.dumps(
        {"fields": [field_entry("a", "ndarray"), field_entry("b", "int")]}
    )

    with pytest.raises(AmbiguousInputSchemaError):
        run_pipeline(notebook, functions, ["a", "b"], schema_response)


def test_malformed_schema_response_is_rejected():
    notebook = {
        "notebook_id": "nb-7",
        "cells": [{"cell_type": "code", "source": "def add(a, b):\n    return a + b"}],
    }
    functions = [{"name": "add", "cell_index": 0}]

    with pytest.raises(MalformedSchemaResponseError):
        run_pipeline(notebook, functions, ["a", "b"], "the fields are a and b")

    with pytest.raises(MalformedSchemaResponseError):
        run_pipeline(notebook, functions, ["a", "b"], json.dumps({"fields": [field_entry("a", "int")]}))


def test_schema_validation():
    validate = LLMInputSchemaService.validate

    valid = LLMInputSchema(
        candidate_id="c-1",
        fields=["a", "b"],
        types={"a": "int", "b": "float"},
        required=["a"],
        defaults={"b": 1.0},
        constraints={"a": {"min": 0}},
    )
    assert validate(valid) is True

    missing_type = LLMInputSchema(
        candidate_id="c-1", fields=["a", "b"], types={"a": "int"}, required=["a"], defaults={}, constraints={}
    )
    with pytest.raises(InvalidSchemaError):
        validate(missing_type)

    bad_type = LLMInputSchema(
        candidate_id="c-1",
        fields=["a"],
        types={"a": "ndarray"},
        required=["a"],
        defaults={},
        constraints={},
    )
    with pytest.raises(InvalidSchemaError):
        validate(bad_type)

    required_with_default = LLMInputSchema(
        candidate_id="c-1",
        fields=["a"],
        types={"a": "int"},
        required=["a"],
        defaults={"a": 1},
        constraints={},
    )
    with pytest.raises(InvalidSchemaError):
        validate(required_with_default)

    unknown_field_in_constraints = LLMInputSchema(
        candidate_id="c-1",
        fields=["a"],
        types={"a": "int"},
        required=["a"],
        defaults={},
        constraints={"z": {"min": 0}},
    )
    with pytest.raises(InvalidSchemaError):
        validate(unknown_field_in_constraints)
