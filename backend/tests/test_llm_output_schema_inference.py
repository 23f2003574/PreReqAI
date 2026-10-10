import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.output_schema import (
    ContradictoryOutputSchemaError,
    InvalidOutputSchemaError,
    LLMOutputSchema,
    LLMOutputSchemaService,
    MalformedOutputSchemaResponseError,
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
    schema_service = LLMOutputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )

    return notebook_analysis_service, candidate_service, schema_service


def field_entry(name, field_type, nullable=False, structure=None, contradictory=False):
    return {
        "name": name,
        "type": field_type,
        "nullable": nullable,
        "structure": structure or {},
        "contradictory": contradictory,
    }


def run_pipeline(notebook, functions, candidate_outputs, schema_response=None):
    analysis_response = json.dumps({"imports": [], "functions": functions, "dependencies": []})
    candidate_response = json.dumps(
        {
            "candidates": [
                {
                    "function_name": functions[0]["name"],
                    "inputs": [],
                    "outputs": candidate_outputs,
                    "confidence": 0.9,
                    "rationale": "Simple pure function.",
                }
            ]
        }
    )

    script = [make_response(analysis_response), make_response(candidate_response)]
    if schema_response is not None:
        script.append(make_response(schema_response))

    notebook_analysis_service, candidate_service, schema_service = build_env(script)
    analysis = notebook_analysis_service.analyze(notebook)
    candidates = candidate_service.analyze(analysis.analysis_id)
    schema = schema_service.infer(candidates[0].candidate_id)
    return schema_service, schema, candidates[0]


def test_primitive_output_preserved_from_annotation():
    notebook = {
        "notebook_id": "nb-1",
        "cells": [{"cell_type": "code", "source": "def add(a: int, b: int) -> int:\n    return a + b"}],
    }
    functions = [{"name": "add", "cell_index": 0}]
    schema_response = json.dumps({"fields": [field_entry("result", "str")]})

    _, schema, _ = run_pipeline(notebook, functions, ["result"], schema_response)

    assert schema.types == {"result": "int"}
    assert schema.nullable == []
    assert schema.structure == {}


def test_object_output_from_literal_return():
    notebook = {
        "notebook_id": "nb-2",
        "cells": [{"cell_type": "code", "source": 'def make_point():\n    return {"x": 1, "y": 2}'}],
    }
    functions = [{"name": "make_point", "cell_index": 0}]
    schema_response = json.dumps({"fields": [field_entry("result", "int")]})

    _, schema, _ = run_pipeline(notebook, functions, ["result"], schema_response)

    assert schema.types == {"result": "dict"}
    assert schema.structure == {"result": {"type": "object", "properties": {"x": "int", "y": "int"}}}


def test_list_of_objects_output_is_nested():
    notebook = {
        "notebook_id": "nb-3",
        "cells": [
            {
                "cell_type": "code",
                "source": (
                    "def make_rows():\n"
                    "    return [{\"id\": 1, \"value\": 1.5}, {\"id\": 2, \"value\": 2.5}]"
                ),
            }
        ],
    }
    functions = [{"name": "make_rows", "cell_index": 0}]
    schema_response = json.dumps({"fields": [field_entry("rows", "list")]})

    _, schema, _ = run_pipeline(notebook, functions, ["rows"], schema_response)

    assert schema.types == {"rows": "list"}
    assert schema.structure == {
        "rows": {
            "type": "list",
            "items": {"type": "object", "properties": {"id": "int", "value": "float"}},
        }
    }


def test_nullable_output_from_literal_none_return():
    notebook = {
        "notebook_id": "nb-4",
        "cells": [
            {
                "cell_type": "code",
                "source": "def find(x):\n    if x:\n        return x\n    return None",
            }
        ],
    }
    functions = [{"name": "find", "cell_index": 0}]
    schema_response = json.dumps({"fields": [field_entry("result", "str", nullable=False)]})

    _, schema, _ = run_pipeline(notebook, functions, ["result"], schema_response)

    assert schema.nullable == ["result"]
    assert schema.types == {"result": "str"}


def test_contradictory_literal_returns_are_rejected():
    notebook = {
        "notebook_id": "nb-5",
        "cells": [
            {
                "cell_type": "code",
                "source": 'def f(flag):\n    if flag:\n        return 1\n    return "x"',
            }
        ],
    }
    functions = [{"name": "f", "cell_index": 0}]

    with pytest.raises(ContradictoryOutputSchemaError):
        run_pipeline(notebook, functions, ["result"])


def test_llm_flagged_contradictory_usage_is_rejected():
    notebook = {
        "notebook_id": "nb-6",
        "cells": [{"cell_type": "code", "source": "def compute(x):\n    return x"}],
    }
    functions = [{"name": "compute", "cell_index": 0}]
    schema_response = json.dumps({"fields": [field_entry("result", "int", contradictory=True)]})

    with pytest.raises(ContradictoryOutputSchemaError):
        run_pipeline(notebook, functions, ["result"], schema_response)


def test_unrecognized_inferred_type_is_rejected():
    notebook = {
        "notebook_id": "nb-7",
        "cells": [{"cell_type": "code", "source": "def compute(x):\n    return x"}],
    }
    functions = [{"name": "compute", "cell_index": 0}]
    schema_response = json.dumps({"fields": [field_entry("result", "ndarray")]})

    with pytest.raises(ContradictoryOutputSchemaError):
        run_pipeline(notebook, functions, ["result"], schema_response)


def test_malformed_schema_response_is_rejected():
    notebook = {
        "notebook_id": "nb-8",
        "cells": [{"cell_type": "code", "source": "def compute(x):\n    return x"}],
    }
    functions = [{"name": "compute", "cell_index": 0}]

    with pytest.raises(MalformedOutputSchemaResponseError):
        run_pipeline(notebook, functions, ["result"], "the output is an int")

    with pytest.raises(MalformedOutputSchemaResponseError):
        run_pipeline(notebook, functions, ["result"], json.dumps({"fields": []}))


def test_schema_validation():
    validate = LLMOutputSchemaService.validate

    valid = LLMOutputSchema(
        candidate_id="c-1",
        fields=["a", "b"],
        types={"a": "int", "b": "list"},
        nullable=["a"],
        structure={"b": {"type": "list", "items": "int"}},
    )
    assert validate(valid) is True

    missing_type = LLMOutputSchema(
        candidate_id="c-1", fields=["a", "b"], types={"a": "int"}, nullable=[], structure={}
    )
    with pytest.raises(InvalidOutputSchemaError):
        validate(missing_type)

    bad_type = LLMOutputSchema(
        candidate_id="c-1", fields=["a"], types={"a": "ndarray"}, nullable=[], structure={}
    )
    with pytest.raises(InvalidOutputSchemaError):
        validate(bad_type)

    nullable_unknown_field = LLMOutputSchema(
        candidate_id="c-1", fields=["a"], types={"a": "int"}, nullable=["z"], structure={}
    )
    with pytest.raises(InvalidOutputSchemaError):
        validate(nullable_unknown_field)

    structure_on_primitive = LLMOutputSchema(
        candidate_id="c-1",
        fields=["a"],
        types={"a": "int"},
        nullable=[],
        structure={"a": {"type": "object", "properties": {}}},
    )
    with pytest.raises(InvalidOutputSchemaError):
        validate(structure_on_primitive)
